# (ไฟล์นี้ต้องบันทึกเป็น UTF-8 แบบมี BOM ไม่อย่างนั้น PowerShell 5 อ่านคำค้นภาษาไทยเพี้ยน)
# ให้ Microsoft Word นับหน้าของไฟล์เล่ม (ใช้โดย md2docx.py --with-word)
# ผล = <โฟลเดอร์>/_pages.json : { "ชื่อไฟล์": { "pages": จำนวนหน้า, "paras": [[ข้อความต้นย่อหน้า, หน้าที่ (นับจาก 1 ในไฟล์)], ...] } }
# จดเฉพาะย่อหน้าที่สารบัญต้องใช้ (หัวบท หัวข้อ N.M ตาราง รูป บทคัดย่อ บรรณานุกรม) · เปิดไฟล์แบบอ่านอย่างเดียว ไม่แก้ไฟล์
param([Parameter(Mandatory = $true)][string]$Dir)
$pattern = '^(บทที่|\d+\.\d+ |ตารางที่|รูปที่|บทคัดย่อ|ABSTRACT|บรรณานุกรม|กิตติกรรมประกาศ)'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$result = [ordered]@{}
try {
    foreach ($f in Get-ChildItem -Path $Dir -Filter '*.docx' | Sort-Object Name) {
        $doc = $word.Documents.Open($f.FullName, $false, $true)
        $paras = @()
        foreach ($p in $doc.Paragraphs) {
            $t = $p.Range.Text.Trim()
            if ($t.Length -gt 0 -and $t.Length -lt 200 -and $t -match $pattern) {
                $paras += , @($t, $p.Range.Information(3))  # 3 = wdActiveEndPageNumber
            }
        }
        $result[$f.Name] = [ordered]@{ pages = $doc.ComputeStatistics(2); paras = $paras }  # 2 = wdStatisticPages
        $doc.Close(0)
        Write-Host "$($f.Name): $($result[$f.Name].pages) pages"
    }
} finally {
    $word.Quit()
}
$result | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $Dir '_pages.json') -Encoding utf8
