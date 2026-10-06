$ErrorActionPreference = 'Stop'

py -3.14 -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed.' }

py -3.14 -m PyInstaller --clean --noconfirm --onedir --name vnc-mcp --paths src `
  --collect-all vncdotool `
  --collect-submodules twisted.internet `
  --collect-submodules twisted.protocols `
  --collect-submodules twisted.python `
  --collect-submodules mcp.server.fastmcp `
  --collect-submodules mcp.server.lowlevel `
  --collect-all PIL main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$oneFileDist = Join-Path (Get-Location) 'dist\onefile'
$oneFileBuild = Join-Path (Get-Location) 'build\onefile'
py -3.14 -m PyInstaller --clean --noconfirm --onefile --name vnc-mcp --distpath $oneFileDist --workpath $oneFileBuild --paths src `
  --collect-all vncdotool `
  --collect-submodules twisted.internet `
  --collect-submodules twisted.protocols `
  --collect-submodules twisted.python `
  --collect-submodules mcp.server.fastmcp `
  --collect-submodules mcp.server.lowlevel `
  --collect-all PIL main.py
if ($LASTEXITCODE -ne 0) { throw 'Single-file PyInstaller build failed.' }
Copy-Item -LiteralPath (Join-Path $oneFileDist 'vnc-mcp.exe') -Destination '.\dist\vnc-mcp.exe' -Force
Copy-Item -LiteralPath '.\README.md' -Destination '.\dist\README.md' -Force
Copy-Item -LiteralPath '.\LICENSE' -Destination '.\dist\LICENSE' -Force
Copy-Item -LiteralPath '.\NOTICE' -Destination '.\dist\NOTICE' -Force
Copy-Item -LiteralPath '.\README.md' -Destination '.\dist\vnc-mcp\README.md' -Force
Copy-Item -LiteralPath '.\LICENSE' -Destination '.\dist\vnc-mcp\LICENSE' -Force
Copy-Item -LiteralPath '.\NOTICE' -Destination '.\dist\vnc-mcp\NOTICE' -Force

$archive = Join-Path (Get-Location) 'dist\vnc-mcp-win-x64.zip'
Compress-Archive -Path '.\dist\vnc-mcp', '.\dist\vnc-mcp.exe', '.\dist\README.md', '.\dist\LICENSE', '.\dist\NOTICE' -DestinationPath $archive -Force
Write-Host "Package created: $archive"
