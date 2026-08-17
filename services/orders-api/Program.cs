using System.Collections.Concurrent;
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Net.Http.Json;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);
const string ServiceName = "orders-api";
var resource = ResourceBuilder.CreateDefault().AddService(ServiceName, serviceVersion: "1.0.0").AddAttributes(new[] { new KeyValuePair<string, object>("deployment.environment.name", "local") });
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService(ServiceName, serviceVersion: "1.0.0"))
    .WithTracing(t => t.AddSource("SignalOps.Orders").AddAspNetCoreInstrumentation().AddHttpClientInstrumentation().AddOtlpExporter())
    .WithMetrics(m => m.AddMeter("SignalOps.Orders").AddAspNetCoreInstrumentation().AddHttpClientInstrumentation().AddOtlpExporter());
builder.Logging.AddJsonConsole();
builder.Logging.AddOpenTelemetry(o => { o.SetResourceBuilder(resource); o.IncludeScopes = true; o.AddOtlpExporter(); });
builder.Services.AddHttpClient("inventory", c => { c.BaseAddress = new(builder.Configuration["INVENTORY_URL"] ?? "http://localhost:8102"); c.Timeout = TimeSpan.FromSeconds(3); });
builder.Services.AddHttpClient("payments", c => { c.BaseAddress = new(builder.Configuration["PAYMENTS_URL"] ?? "http://localhost:8101"); c.Timeout = TimeSpan.FromSeconds(3); });

var app = builder.Build();
var orders = new ConcurrentDictionary<string, Order>();
var byKey = new ConcurrentDictionary<string, string>();
var faults = new ConcurrentDictionary<string, DateTimeOffset>();
var meter = new Meter("SignalOps.Orders", "1.0.0");
var created = meter.CreateCounter<long>("signalops.orders.created");
var activity = new ActivitySource("SignalOps.Orders");

app.Use(async (context, next) => {
    var correlationId = context.Request.Headers["X-Correlation-ID"].FirstOrDefault() ?? Guid.NewGuid().ToString("N");
    context.Request.Headers["X-Correlation-ID"] = correlationId;
    context.Response.Headers["X-Correlation-ID"] = correlationId;
    using (app.Logger.BeginScope(new Dictionary<string, object> { ["correlation_id"] = correlationId, ["service_name"] = ServiceName })) { await next(); }
});

app.MapGet("/health/live", () => Results.Ok(new { status = "live" }));
app.MapGet("/health/ready", () => Results.Ok(new { status = "ready" }));
app.MapGet("/api/v1/orders/{id}", (string id) => orders.TryGetValue(id, out var order) ? Results.Ok(order) : Results.NotFound());

app.MapPost("/api/v1/orders", async (HttpRequest request, CreateOrder input, IHttpClientFactory clients, ILogger<Program> log) => {
    var idempotencyKey = request.Headers["Idempotency-Key"].FirstOrDefault();
    if (string.IsNullOrWhiteSpace(idempotencyKey)) return Results.BadRequest(new { code = "idempotency_key_required", message = "Idempotency-Key is required" });
    if (byKey.TryGetValue(idempotencyKey, out var existingId) && orders.TryGetValue(existingId, out var existing)) return Results.Ok(existing);

    var order = new Order(Guid.NewGuid().ToString("N"), input.ProductId, input.Quantity, input.Amount, "pending", DateTimeOffset.UtcNow);
    orders[order.Id] = order; byKey[idempotencyKey] = order.Id;
    if (Active("slow-database")) { using var dbSpan = activity.StartActivity("db.orders.insert", ActivityKind.Client); dbSpan?.SetTag("db.system", "postgresql"); await Task.Delay(1500); }

    try {
        var inventory = clients.CreateClient("inventory");
        using var reserve = new HttpRequestMessage(HttpMethod.Post, "/api/v1/reservations") { Content = JsonContent.Create(new { orderId = order.Id, productId = input.ProductId, quantity = input.Quantity }) };
        reserve.Headers.TryAddWithoutValidation("Idempotency-Key", idempotencyKey);
        CopyCorrelation(request, reserve);
        var inventoryResponse = await inventory.SendAsync(reserve);
        if (!inventoryResponse.IsSuccessStatusCode) {
            var rejected = order with { Status = "rejected" }; orders[order.Id] = rejected; created.Add(1, new KeyValuePair<string, object?>("result", "inventory_rejected"));
            log.LogWarning("Inventory reservation failed for order {OrderId} with {StatusCode}", order.Id, (int)inventoryResponse.StatusCode);
            return Results.Json(rejected, statusCode: 409);
        }

        if (Active("payment-latency")) { using var dependencySpan = activity.StartActivity("orders-to-payments.injected-latency", ActivityKind.Client); dependencySpan?.SetTag("fault.type", "dependency_path_latency"); await Task.Delay(1100); }
        var payments = clients.CreateClient("payments");
        using var authorise = new HttpRequestMessage(HttpMethod.Post, "/api/v1/payments/authorizations") { Content = JsonContent.Create(new { orderId = order.Id, amount = input.Amount }) };
        authorise.Headers.TryAddWithoutValidation("Idempotency-Key", idempotencyKey); CopyCorrelation(request, authorise);
        var paymentResponse = await payments.SendAsync(authorise);
        if (!paymentResponse.IsSuccessStatusCode) {
            await inventory.PostAsJsonAsync("/api/v1/reservations/release", new { orderId = order.Id });
            var failed = order with { Status = "payment_failed" }; orders[order.Id] = failed; created.Add(1, new KeyValuePair<string, object?>("result", "payment_failed"));
            log.LogError("Payment authorization failed for order {OrderId} with {StatusCode}", order.Id, (int)paymentResponse.StatusCode);
            return Results.Json(failed, statusCode: 402);
        }
        var confirmed = order with { Status = "confirmed" }; orders[order.Id] = confirmed; created.Add(1, new KeyValuePair<string, object?>("result", "confirmed"));
        log.LogInformation("Order {OrderId} confirmed", order.Id); return Results.Created($"/api/v1/orders/{order.Id}", confirmed);
    } catch (TaskCanceledException) {
        var failed = order with { Status = "dependency_timeout" }; orders[order.Id] = failed; created.Add(1, new KeyValuePair<string, object?>("result", "dependency_timeout"));
        return Results.Json(failed, statusCode: 504);
    }
});

app.MapPost("/api/v1/demo/faults", (FaultRequest fault, HttpRequest request) => {
    if (!Authorised(request)) return Results.Unauthorized();
    if (fault.Type is not ("slow-database" or "payment-latency") || fault.TtlSeconds is < 30 or > 600) return Results.BadRequest(new { code = "invalid_fault" });
    faults[fault.Type] = DateTimeOffset.UtcNow.AddSeconds(fault.TtlSeconds); return Results.Ok(new { fault.Type, expiresAt = faults[fault.Type] });
});
app.MapDelete("/api/v1/demo/faults/{type}", (string type, HttpRequest request) => Authorised(request) ? (faults.TryRemove(type, out _), Results.NoContent()).Item2 : Results.Unauthorized());

app.Run();

bool Active(string type) => faults.TryGetValue(type, out var expiry) && expiry > DateTimeOffset.UtcNow;
bool Authorised(HttpRequest request) => Environment.GetEnvironmentVariable("DEMO_MODE")?.Equals("true", StringComparison.OrdinalIgnoreCase) != false && request.Headers["X-Fault-Control-Token"] == (Environment.GetEnvironmentVariable("FAULT_CONTROL_TOKEN") ?? "signalops-local-demo");
static void CopyCorrelation(HttpRequest source, HttpRequestMessage target) { if (source.Headers.TryGetValue("X-Correlation-ID", out var value)) target.Headers.TryAddWithoutValidation("X-Correlation-ID", value.ToString()); }

record CreateOrder(string ProductId, int Quantity, decimal Amount);
record Order(string Id, string ProductId, int Quantity, decimal Amount, string Status, DateTimeOffset CreatedAt);
record FaultRequest(string Type, int TtlSeconds);

public partial class Program { }
