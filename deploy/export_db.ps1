# Makes a consistent copy of the collected database on the Desktop, safe to take while
# the collectors are running (SQLite online backup, not a file copy of a live database).
# Copy the resulting file back to the laptop over Remote Desktop for the Gate 2 run.

$proj = Split-Path -Parent $PSScriptRoot
$py = "C:\Python312\python.exe"
$dest = Join-Path ([Environment]::GetFolderPath("Desktop")) ("candidates-{0:yyyyMMdd-HHmm}.sqlite" -f (Get-Date))
& $py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); print('rows in books:', s.execute('select count(*) from books').fetchone()[0])" "$proj\data\candidates.sqlite" $dest
Write-Host "Exported -> $dest"
