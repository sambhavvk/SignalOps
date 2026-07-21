using System.Collections.Concurrent;
using System.Diagnostics.Metrics;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);
const string ServiceName = "payments-api";
var resource = ResourceBuilder.CreateDefault().AddService(ServiceName, serviceVersion: "1.0.0");
builder.Services.AddOpenTelemetry().ConfigureResource(r => r.AddService(ServiceName, serviceVersion: "1.0.0"))
    .WithTracing(t => t.AddAspNetCoreInstrumentation().AddOtlpExporter())
    .WithMetrics(m => m.AddMeter("SignalOps.Payments").AddAspNetCoreInstrumentation().AddOtlpExporter());
builder.Logging.AddJsonConsole();
builder.Logging.AddOpenTelemetry(o => { o.SetResourceBuilder(resource); o.IncludeScopes = true; o.AddOtlpExporter(); });

var app = builder.Build();
var attempts = new ConcurrentDictionary<string, PaymentAttempt>();
var faults = new ConcurrentDictionary<string, DateTimeOffset>();
var meter = new Meter("SignalOps.Payments", "1.0.0");
var authorised = meter.CreateCounter<long>("signalops.payments.authorized");

app.Use(async (context, next) => {
    var correlation = context.Request.Headers["X-Correlation-ID"].FirstOrDefault() ?? Guid.NewGuid().ToString("N");
    context.Request.Headers["X-Correlation-ID"] = correlation; context.Response.Headers["X-Correlation-ID"] = correlation;
    using (app.Logger.BeginScope(new Dictionary<string, object> { ["correlation_id"] = correlation, ["service_name"] = ServiceName })) await next();
});

app.MapGet("/health/live", () => Results.Ok(new { status = "live" }));
app.MapGet("/health/ready", () => Results.Ok(new { status = "ready" }));
app.MapPost("/api/v1/payments/authorizations", (PaymentRequest payment, HttpRequest request, ILogger<Program> log) => {
    var key = request.Headers["Idempotency-Key"].FirstOrDefault();
    if (string.IsNullOrWhiteSpace(key)) return Results.BadRequest(new { code = "idempotency_key_required" });
    if (attempts.TryGetValue(key, out var existing)) return Results.Ok(existing);

    var shouldFail = Active("error-surge") && DeterministicFailure(key);
    var attempt = new PaymentAttempt(Guid.NewGuid().ToString("N"), payment.OrderId, payment.Amount, shouldFail ? "failed" : "authorized", DateTimeOffset.UtcNow);
    attempts[key] = attempt;
    if (shouldFail) {
        authorised.Add(1, new KeyValuePair<string, object?>("result", "service_unavailable"));
        log.LogError("Payment authorization returned service_unavailable for order {OrderId}", payment.OrderId);
        return Results.Json(new { code = "payment_service_unavailable", message = "Deterministic demo failure" }, statusCode: 503);
    }
    authorised.Add(1, new KeyValuePair<string, object?>("result", "authorized")); log.LogInformation("Payment authorized for order {OrderId}", payment.OrderId);
    return Results.Ok(attempt);
});

app.MapPost("/api/v1/demo/faults", (FaultRequest fault, HttpRequest request) => {
    if (!Authorised(request)) return Results.Unauthorized();
    if (fault.Type != "error-surge" || fault.TtlSeconds is < 30 or > 600) return Results.BadRequest(new { code = "invalid_fault" });
    faults[fault.Type] = DateTimeOffset.UtcNow.AddSeconds(fault.TtlSeconds); return Results.Ok(new { fault.Type, expiresAt = faults[fault.Type] });
});
app.MapDelete("/api/v1/demo/faults/{type}", (string type, HttpRequest request) => Authorised(request) ? (faults.TryRemove(type, out _), Results.NoContent()).Item2 : Results.Unauthorized());
app.Run();

bool Active(string type) => faults.TryGetValue(type, out var expiry) && expiry > DateTimeOffset.UtcNow;
static bool DeterministicFailure(string key) => Math.Abs(key.GetHashCode(StringComparison.Ordinal)) % 10 < 6;
bool Authorised(HttpRequest request) => Environment.GetEnvironmentVariable("DEMO_MODE")?.Equals("true", StringComparison.OrdinalIgnoreCase) != false && request.Headers["X-Fault-Control-Token"] == (Environment.GetEnvironmentVariable("FAULT_CONTROL_TOKEN") ?? "signalops-local-demo");
record PaymentRequest(string OrderId, decimal Amount);
record PaymentAttempt(string Id, string OrderId, decimal Amount, string Status, DateTimeOffset CreatedAt);
record FaultRequest(string Type, int TtlSeconds);
public partial class Program { }
