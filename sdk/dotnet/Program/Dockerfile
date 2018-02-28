FROM microsoft/dotnet AS build-env
WORKDIR /app

# RUN ls -la
# # Copy csproj and restore as distinct layers

# RUN dotnet restore Program.csproj
# RUN dotnet build

COPY . /app/

RUN pwd
RUN ls -la

RUN dotnet publish Program/Program.csproj -c Release --framework netcoreapp2.0

ENTRYPOINT ["dotnet", "Program.dll"]