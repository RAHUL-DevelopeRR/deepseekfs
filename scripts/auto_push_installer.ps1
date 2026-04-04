$isccProcess = Get-Process ISCC -ErrorAction SilentlyContinue
if ($isccProcess) {
    Write-Host "Waiting for Inno Setup Compiler (ISCC) to finish compressing..."
    $isccProcess | Wait-Process
}

Write-Host "ISCC finished. Configuring Git LFS to track large .exe files..."
git lfs track "*.exe"
git add .gitattributes
git add -f installer_output\NeuronSetup_v4.2.exe

Write-Host "Committing..."
git commit -m "build: compile neuron setup installer v4.2"

Write-Host "Pushing to origin dv-4.2.2..."
git push origin dv-4.2.2

Write-Host "Done!"
