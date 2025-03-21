@echo off
echo Starting CV Analysis Tool...

:: Check if Python virtual environment exists
if not exist .venv\ (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
    call .venv\Scripts\activate
    echo Installing Python dependencies...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

:: Check if .env file exists
if not exist .env (
    echo .env file not found. Creating a template...
    echo API_USERNAME=your_username_here> .env
    echo API_PASSWORD=your_password_here>> .env
    echo API_BASE_URL=https://hr-demo-app.ambitiousriver-e696f55c.australiaeast.azurecontainerapps.io/api/v1>> .env
    echo REVISION_ID=5ccc4a42-1e24-4b82-a550-e7e9c6ffa48b>> .env
    echo # Add your full Azure Blob Storage URL with SAS token>> .env
    echo AZURE_BLOB_STORAGE_URL=https://storageaccount.blob.core.windows.net/container/blob?sastoken>> .env
    echo # Azure OpenAI API settings>> .env
    echo AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com>> .env
    echo AZURE_OPENAI_KEY=your_api_key_here>> .env
    echo AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini>> .env
    echo Please edit the .env file with your actual credentials before proceeding.
    echo Especially ensure the Azure OpenAI API credentials are provided for CV comparison summary.
    exit /b
)

:: Start Streamlit app
echo Starting Streamlit app...
streamlit run app.py

echo App closed. Goodbye!