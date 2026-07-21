FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /src
COPY payments-api.csproj .
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /out --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine
WORKDIR /app
COPY --from=build /out .
EXPOSE 8080
ENTRYPOINT ["dotnet", "payments-api.dll"]
