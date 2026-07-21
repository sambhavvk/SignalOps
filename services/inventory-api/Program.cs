using System.Collections.Concurrent;
using System.Diagnostics.Metrics;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);
const string ServiceName = "inventory-api";
var resource = ResourceBuilder.CreateDefault().AddService(ServiceName, serviceVersion: "1.0.0");
builder.Services.AddOpenTelemetry().ConfigureResource(r => r.AddService(ServiceName, serviceVersion: "1.0.0"))
    .WithTracing(t => t.AddAspNetCoreInstrumentation().AddOtlpExporter())
    .WithMetrics(m => m.AddMeter("SignalOps.Inventory").AddAspNetCoreInstrumentation().AddOtlpExporter());
builder.Logging.AddJsonConsole();
builder.Logging.AddOpenTelemetry(o => { o.SetResourceBuilder(resource); o.IncludeScopes = true; o.AddOtlpExporter(); });

var app = builder.Build();
var stock = new ConcurrentDictionary<string, int>(new[] { new KeyValuePair<string, int>("sku-signal-lamp", 1000) });
var reservations = new ConcurrentDictionary<string, Reservation>();
var faults = new ConcurrentDictionary<string, DateTimeOffset>();
var meter = new Meter("SignalOps.Inventory", "1.0.0");
var reservationMetric = meter.CreateCounter<long>("signalops.inventory.reservations");

app.Use(async (context, next) => {
    var correlation = context.Request.Headers["X-Correlation-ID"].FirstOrDefault() ?? Guid.NewGuid().ToString("N");
    context.Request.Headers["X-Correlation-ID"] = correlation; context.Response.Headers["X-Correlation-ID"] = correlation;
    using (app.Logger.BeginScope(new Dictionary<string, object> { ["correlation_id"] = correlation, ["service_name"] = ServiceName })) await next();
});

app.MapGet("/health/live", () => Results.Ok(new { status = "live" }));
app.MapGet("/health/ready", () => Active("unavailable") ? Results.Json(new { status = "unavailable" }, statusCode: 503) : Results.Ok(new { status = "ready" }));
app.MapGet("/api/v1/products", () => stock.Select(x => new { id = x.Key, available = x.Value }));
app.MapPost("/api/v1/reservations", (ReservationRequest input, HttpRequest request, ILogger<Program> log) => {
    if (Active("unavailable")) { reservationMetric.Add(1, new KeyValuePair<string, object?>("result", "unavailable")); log.LogError("Inventory reservation rejected because service is unavailable"); return Results.Json(new { code = "inventory_unavailable" }, statusCode: 503); }
    var key = request.Headers["Idempotency-Key"].FirstOrDefault() ?? input.OrderId;
    if (reservations.TryGetValue(key, out var existing)) return Results.Ok(existing);
    if (!stock.TryGetValue(input.ProductId, out var available) || available < input.Quantity) { reservationMetric.Add(1, new KeyValuePair<string, object?>("result", "insufficient")); return Results.Conflict(new { code = "insufficient_inventory" }); }
    if (!stock.TryUpdate(input.ProductId, available - input.Quantity, available)) return Results.Json(new { code = "reservation_conflict" }, statusCode: 409);
    var reservation = new Reservation(Guid.NewGuid().ToString("N"), input.OrderId, input.ProductId, input.Quantity, "reserved");
    reservations[key] = reservation; reservationMetric.Add(1, new KeyValuePair<string, object?>("result", "reserved")); log.LogInformation("Inventory reserved for order {OrderId}", input.OrderId); return Results.Created($"/api/v1/reservations/{reservation.Id}", reservation);
});
app.MapPost("/api/v1/reservations/release", (ReleaseRequest input) => {
    var entry = reservations.FirstOrDefault(x => x.Value.OrderId == input.OrderId);
    if (entry.Value is null || entry.Value.Status == "released") return Results.NoContent();
    stock.AddOrUpdate(entry.Value.ProductId, entry.Value.Quantity, (_, current) => current + entry.Value.Quantity);
    reservations[entry.Key] = entry.Value with { Status = "released" }; reservationMetric.Add(1, new KeyValuePair<string, object?>("result", "released")); return Results.NoContent();
});
app.MapPost("/api/v1/demo/faults", (FaultRequest fault, HttpRequest request) => {
    if (!Authorised(request)) return Results.Unauthorized();
    if (fault.Type != "unavailable" || fault.TtlSeconds is < 30 or > 600) return Results.BadRequest(new { code = "invalid_fault" });
    faults[fault.Type] = DateTimeOffset.UtcNow.AddSeconds(fault.TtlSeconds); return Results.Ok(new { fault.Type, expiresAt = faults[fault.Type] });
});
app.MapDelete("/api/v1/demo/faults/{type}", (string type, HttpRequest request) => Authorised(request) ? (faults.TryRemove(type, out _), Results.NoContent()).Item2 : Results.Unauthorized());
app.Run();

bool Active(string type) => faults.TryGetValue(type, out var expiry) && expiry > DateTimeOffset.UtcNow;
bool Authorised(HttpRequest request) => Environment.GetEnvironmentVariable("DEMO_MODE")?.Equals("true", StringComparison.OrdinalIgnoreCase) != false && request.Headers["X-Fault-Control-Token"] == (Environment.GetEnvironmentVariable("FAULT_CONTROL_TOKEN") ?? "signalops-local-demo");
record ReservationRequest(string OrderId, string ProductId, int Quantity);
record ReleaseRequest(string OrderId);
record Reservation(string Id, string OrderId, string ProductId, int Quantity, string Status);
record FaultRequest(string Type, int TtlSeconds);
public partial class Program { }
