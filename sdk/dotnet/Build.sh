#/bin/bash

dotnet restore

# dotnet publish -c Release --framework netcoreapp2.0 --runtime osx-x64 Sdk/Sdk.csproj
dotnet publish -c Release --framework netstandard2.0 Sdk/Sdk.csproj

nuget pack Sawtooth.Sdk.nuspec