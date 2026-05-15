
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | 
        Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 } | 
        Select-Object -First 1

    [void][Windows.Security.Cryptography.CryptographicBuffer, Windows.Security.Cryptography, ContentType = WindowsRuntime]
    [void][Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    [void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    [void][Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]

    function Await($asyncAction) {
        $task = $asyncAction.AsTask()
        while (-not $task.IsCompleted) {
            Start-Sleep -Milliseconds 10
        }
        return $task.Result
    }

    try {
        # Native Windows 10/11 OCR API
        $filePath = "c:\\Users\\Madhu\\OneDrive\\Desktop\\Suraksha Hackathon\\backend\\static\\heatmaps\\e606e838-3665-4d65-b6fd-1aab180b284e_heatmap.png"
        $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($filePath)
        while (-not $file.IsCompleted) { Start-Sleep -Milliseconds 50 }
        $file = $file.GetResults()

        $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
        while (-not $stream.IsCompleted) { Start-Sleep -Milliseconds 50 }
        $stream = $stream.GetResults()

        $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
        while (-not $decoder.IsCompleted) { Start-Sleep -Milliseconds 50 }
        $decoder = $decoder.GetResults()

        $bitmap = $decoder.GetSoftwareBitmapAsync()
        while (-not $bitmap.IsCompleted) { Start-Sleep -Milliseconds 50 }
        $bitmap = $bitmap.GetResults()

        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        if (-not $engine) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage("en-US")
        }

        $ocrResult = $engine.RecognizeAsync($bitmap)
        while (-not $ocrResult.IsCompleted) { Start-Sleep -Milliseconds 50 }
        $ocrResult = $ocrResult.GetResults()

        Write-Output "OCR_START>>>"
        Write-Output $ocrResult.Text
        Write-Output "<<<OCR_END"
    } catch {
        Write-Output $_.Exception.Message
        Write-Output $_.ScriptStackTrace
    }
    