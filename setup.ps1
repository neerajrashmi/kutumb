# Set execution policy (only needed once, but safe here)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1

Write-Host "Starting Django development server..." -ForegroundColor Green
python manage.py runserver
