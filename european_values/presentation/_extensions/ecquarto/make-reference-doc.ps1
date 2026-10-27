# Builds ec-corporate.pptx (the Pandoc reference document used for `format: pptx`)
# and ec-bg-end.png (background of the {.end} slide).
#
# Requires Microsoft PowerPoint (COM automation) and Quarto.
# Run from the repository folder:   powershell -File make-reference-doc.ps1

$ErrorActionPreference = "Stop"
trap { Write-Host "ERROR at line $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())"; Write-Host $_.Exception.Message; break }
Add-Type -AssemblyName System.Drawing
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outPptx = Join-Path $root "ec-corporate.pptx"

# EC colours (COM wants BGR packed integers)
function RGB($r, $g, $b) { return $r + ($g * 256) + ($b * 65536) }
$ecBlue  = RGB 0 51 153      # #003399
$ecWhite = RGB 255 255 255
$ecText  = RGB 64 64 64      # #404040
$ecMint  = [System.Drawing.Color]::FromArgb(0xC6, 0xE5, 0xDF)

# ---------------------------------------------------------------------------
# 1. End-slide background: mint fill + CC BY logo (1920x1080, 16:9)
# ---------------------------------------------------------------------------
$bmp = New-Object System.Drawing.Bitmap 1920, 1080
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear($ecMint)
$logo = [System.Drawing.Image]::FromFile((Join-Path $root "cc-by-logo.png"))
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$lw = 246; $lh = 86
# "Thank you" (44 pt) ends ~150 pt of 405 (400 px of 1080); the text resumes ~208 pt (555 px)
$g.DrawImage($logo, 100, 420, $lw, $lh)
$g.Dispose(); $logo.Dispose()
$bmp.Save((Join-Path $root "ec-bg-end.png"), [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

# ---------------------------------------------------------------------------
# 2. Start from Pandoc's default reference document
# ---------------------------------------------------------------------------
if (Test-Path $outPptx) { Remove-Item $outPptx -Force }
& quarto pandoc -o $outPptx --print-default-data-file reference.pptx
if (-not (Test-Path $outPptx)) { throw "quarto pandoc did not produce $outPptx" }

$pp = New-Object -ComObject PowerPoint.Application
try {
$pres = $pp.Presentations.Open($outPptx, $false, $false, $false)
$W = $pres.PageSetup.SlideWidth    # 720 pt
$H = $pres.PageSetup.SlideHeight   # 405 pt
$master = $pres.SlideMaster

# Fonts: Arial everywhere
$master.Theme.ThemeFontScheme.MajorFont(1).Name = "Arial"
$master.Theme.ThemeFontScheme.MinorFont(1).Name = "Arial"

# Master text styles: ppTitleStyle = 2, ppBodyStyle = 3
$title = $master.TextStyles(2).TextFrame.TextRange
$title.Font.Color.RGB = $ecBlue
$title.Font.Bold = -1
$title.Font.Size = 32
$title.ParagraphFormat.Alignment = 1   # ppAlignLeft
$body = $master.TextStyles(3).TextFrame.TextRange
$body.Font.Color.RGB = $ecText
$body.Font.Size = 18

# Link colour = EC blue (theme colour index 11 = hyperlink)
$master.Theme.ThemeColorScheme.Colors(11).RGB = $ecBlue
$master.Theme.ThemeColorScheme.Colors(12).RGB = $ecBlue

function Get-Layout($name) {
  foreach ($l in $master.CustomLayouts) { if ($l.Name -eq $name) { return $l } }
  throw "Layout '$name' not found"
}
function Get-Placeholder($layout, [int[]]$types) {
  foreach ($s in $layout.Shapes) {
    if ($s.Type -eq 14 -and ($types -contains $s.PlaceholderFormat.Type)) { return $s }
  }
  return $null
}
# Placeholder types: 1 title, 2 body, 3 centre title, 4 subtitle, 13 slide number, 15 footer, 16 date

# ---------------------------------------------------------------------------
# 3. Title Slide: blue background, white text, white logo bottom-right
# ---------------------------------------------------------------------------
$lay = Get-Layout "Title Slide"
$lay.FollowMasterBackground = 0
$lay.Background.Fill.Solid()
$lay.Background.Fill.ForeColor.RGB = $ecBlue

$t = Get-Placeholder $lay @(3, 1)
$t.Left = 24; $t.Top = 95; $t.Width = 560; $t.Height = 110
$t.TextFrame.VerticalAnchor = 4           # msoAnchorBottom
$t.TextFrame.TextRange.Font.Color.RGB = $ecWhite
$t.TextFrame.TextRange.Font.Size = 40
$t.TextFrame.TextRange.Font.Bold = 0
$t.TextFrame.TextRange.ParagraphFormat.Alignment = 1

$s = Get-Placeholder $lay @(4, 2)
$s.Left = 24; $s.Top = 215; $s.Width = 560; $s.Height = 120
$s.TextFrame.VerticalAnchor = 1           # msoAnchorTop
$s.TextFrame.TextRange.Font.Color.RGB = $ecWhite
$s.TextFrame.TextRange.Font.Size = 20
$s.TextFrame.TextRange.ParagraphFormat.Alignment = 1

# hide date/footer/slide-number on the title slide
foreach ($ph in @(Get-Placeholder $lay @(13)), (Get-Placeholder $lay @(15)), (Get-Placeholder $lay @(16))) {
  if ($ph) { $ph.Delete() }
}

$logoW = 210; $logoH = $logoW * 226 / 612
$pic = $lay.Shapes.AddPicture((Join-Path $root "ec-logo-white.png"), 0, -1, ($W - 30 - $logoW), ($H - 22 - $logoH), $logoW, $logoH)
$pic.Name = "EC logo"

# ---------------------------------------------------------------------------
# 4. Title and Content (and siblings): emblem bottom-right
# ---------------------------------------------------------------------------
$emblemW = 120; $emblemH = $emblemW * 183 / 302
foreach ($name in @("Title and Content", "Two Content", "Comparison", "Content with Caption", "Title Only", "Blank")) {
  $lay = Get-Layout $name
  $pic = $lay.Shapes.AddPicture((Join-Path $root "ec-emblem.png"), 0, -1, ($W - 26 - $emblemW), ($H - 19 - $emblemH), $emblemW, $emblemH)
  $pic.Name = "EC emblem"
  $t = Get-Placeholder $lay @(1)
  if ($t) { $t.Left = 36; $t.Width = $W - 72; $t.TextFrame.TextRange.ParagraphFormat.Alignment = 1 }
  foreach ($ph in @(Get-Placeholder $lay @(15)), (Get-Placeholder $lay @(16))) { if ($ph) { $ph.Delete() } }
  $n = Get-Placeholder $lay @(13)
  if ($n) { $n.Left = 30; $n.Top = $H - 32; $n.Width = 80; $n.Height = 22
            $n.TextFrame.TextRange.ParagraphFormat.Alignment = 1
            $n.TextFrame.TextRange.Font.Color.RGB = $ecText; $n.TextFrame.TextRange.Font.Size = 12 }
}
# make the content body a little narrower so long lines never run under the emblem
$lay = Get-Layout "Title and Content"
$b = Get-Placeholder $lay @(2, 7)
$b.Left = 36; $b.Width = $W - 72; $b.Height = $H - $b.Top - 60

# ---------------------------------------------------------------------------
# 5. Section Header: blue band on the top 55 %, title + subtitle in the white part
# ---------------------------------------------------------------------------
$lay = Get-Layout "Section Header"
$band = $lay.Shapes.AddShape(1, 0, 0, $W, [math]::Round($H * 0.55, 2))   # msoShapeRectangle
$band.Name = "EC blue band"
$band.Fill.Solid(); $band.Fill.ForeColor.RGB = $ecBlue
$band.Line.Visible = 0
$band.Shadow.Visible = 0
$band.ZOrder(1)   # msoSendToBack
$bodyPh = Get-Placeholder $lay @(2, 7)
if ($bodyPh) { $bodyPh.Delete() }
foreach ($ph in @(Get-Placeholder $lay @(13)), (Get-Placeholder $lay @(15)), (Get-Placeholder $lay @(16))) { if ($ph) { $ph.Delete() } }
$t = Get-Placeholder $lay @(1)
$t.Left = 60; $t.Top = ($H * 0.55) + 18; $t.Width = $W - 120; $t.Height = $H - $t.Top - 20
$t.TextFrame.VerticalAnchor = 1
$t.TextFrame.AutoSize = 0
$t.TextFrame.WordWrap = -1
$t.TextFrame.TextRange.Font.Color.RGB = $ecBlue
$t.TextFrame.TextRange.Font.Size = 36
$t.TextFrame.TextRange.Font.Bold = 0
$t.TextFrame2.TextRange.Font.Allcaps = 0
$t.TextFrame.TextRange.ParagraphFormat.Alignment = 1

$pres.Save()
$pres.Close()
Write-Host "Wrote $outPptx and ec-bg-end.png"
} finally {
  $pp.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp) | Out-Null
}
