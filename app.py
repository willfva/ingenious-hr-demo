import streamlit as st
import requests
import json
import pandas as pd
import uuid
import time
import os
from io import BytesIO
import docx2txt
import pypdf
import base64
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
import re
from azure.storage.blob import BlobServiceClient, ContentSettings
import tempfile

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv(
    "API_BASE_URL", "https://hr-demo-app.ambitiousriver-e696f55c.australiaeast.azurecontainerapps.io/api/v1")
API_USERNAME = os.getenv("API_USERNAME", "")
API_PASSWORD = os.getenv("API_PASSWORD", "")
DEFAULT_REVISION_ID = os.getenv(
    "REVISION_ID", "5ccc4a42-1e24-4b82-a550-e7e9c6ffa48b")
AZURE_BLOB_SAS_TOKEN = os.getenv("AZURE_BLOB_SAS_TOKEN", "")
AZURE_BLOB_STORAGE_URL = os.getenv(
    "AZURE_BLOB_STORAGE_URL", "https://stasydingdevlogkm001.blob.core.windows.net")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "hr-app-data")

# Set page config
st.set_page_config(
    page_title="CV Analysis Tool",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)


class APIClient:
    """Client for interacting with the FastAgent API."""

    def __init__(self):
        pass

    @classmethod
    def create_chat(cls, cv_content: str, thread_id: Optional[str] = None, identifier: Optional[str] = None) -> Dict[str, Any]:
        """Send a CV for analysis and get the results."""
        url = f"{API_BASE_URL}/chat"

        # Format the CV content as required by the API
        user_prompt_data = {
            "revision_id": DEFAULT_REVISION_ID,
            "identifier": identifier or str(uuid.uuid4())[:8],
            "Page_1": cv_content
        }

        # Convert the user_prompt_data to a JSON string
        user_prompt_json = json.dumps(user_prompt_data)

        payload = {
            "thread_id": thread_id or str(uuid.uuid4()),
            "conversation_flow": "hr_insights",
            "user_prompt": user_prompt_json
        }

        try:
            # Use basic authentication from environment variables
            auth = (API_USERNAME, API_PASSWORD)
            response = requests.post(url, json=payload, auth=auth)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"API Error: {str(e)}")
            return {"error": str(e)}

    @classmethod
    def submit_feedback(cls, message_id: str, thread_id: str, positive: bool) -> Dict[str, Any]:
        """Submit feedback on an analysis."""
        url = f"{API_BASE_URL}/messages/{message_id}/feedback"

        payload = {
            "thread_id": thread_id,
            "message_id": message_id,
            "user_id": "streamlit_user",
            "positive_feedback": positive
        }

        try:
            # Use basic authentication
            auth = (API_USERNAME, API_PASSWORD)
            response = requests.put(url, json=payload, auth=auth)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"API Error: {str(e)}")
            return {"error": str(e)}


class AzureBlobClient:
    """Client for interacting with Azure Blob Storage."""

    def __init__(self):
        self.account_url = AZURE_BLOB_STORAGE_URL
        self.sas_token = AZURE_BLOB_SAS_TOKEN
        self.container_name = AZURE_BLOB_CONTAINER

        # Check if SAS token is available
        if not self.sas_token:
            raise ValueError(
                "AZURE_BLOB_SAS_TOKEN environment variable is not set or is empty")

        # Create the BlobServiceClient object
        try:
            self.blob_service_client = BlobServiceClient(
                account_url=f"{self.account_url}?{self.sas_token}"
            )
        except Exception as e:
            raise ValueError(f"Failed to create BlobServiceClient: {str(e)}")

    def upload_blob(self, content: str, blob_name: str, content_type: str = "application/json") -> bool:
        """Upload content to Azure Blob Storage."""
        try:
            # Get a client to interact with the specified blob
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            # Set the content type
            content_settings = ContentSettings(content_type=content_type)

            # Upload the content
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )

            return True
        except Exception as e:
            st.error(f"Azure Blob Error: {str(e)}")
            return False

    def download_blob(self, blob_name: str) -> Optional[str]:
        """Download content from Azure Blob Storage."""
        try:
            # Get a client to interact with the specified blob
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            # Download the blob content
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')

            return content
        except Exception as e:
            st.error(f"Azure Blob Error: {str(e)}")
            return None


def extract_text_from_file(uploaded_file) -> str:
    """Extract text content from various file types."""
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()

    try:
        if file_extension == ".pdf":
            return extract_text_from_pdf(uploaded_file)
        elif file_extension == ".docx":
            return extract_text_from_docx(uploaded_file)
        elif file_extension in [".txt", ".md", ".json"]:
            return uploaded_file.getvalue().decode("utf-8")
        else:
            return f"Unsupported file type: {file_extension}"
    except Exception as e:
        return f"Error extracting text: {str(e)}"


def extract_text_from_pdf(uploaded_file) -> str:
    """Extract text from PDF file."""
    pdf_reader = pypdf.PdfReader(BytesIO(uploaded_file.getvalue()))
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        text += pdf_reader.pages[page_num].extract_text()

    return text


def extract_text_from_docx(uploaded_file) -> str:
    """Extract text from DOCX file."""
    return docx2txt.process(BytesIO(uploaded_file.getvalue()))


def create_download_link(content, filename, text):
    """Create a download link for exporting results."""
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'
    return href


def convert_text_to_job_criteria_json(text: str) -> Dict[str, Any]:
    """Convert extracted text from document to a simple job criteria JSON format.

    This just takes the extracted text and places it in one string value in the JSON,
    without attempting to parse specific fields.
    """
    # Simple conversion to a JSON object with a single text field
    criteria = {
        "job_criteria_text": text
    }

    return criteria


def update_job_criteria_in_azure(job_criteria: Dict[str, Any]) -> bool:
    """Update the job_criteria.json file in Azure Blob Storage."""
    try:
        # Check if SAS token is provided
        if not AZURE_BLOB_SAS_TOKEN:
            st.error(
                "Azure Blob SAS token is missing. Please add it to your .env file.")
            return False

        # Initialize the blob client
        blob_client = AzureBlobClient()

        # Convert the job criteria to JSON
        job_criteria_json = json.dumps(job_criteria, indent=2)

        # Upload to Azure Blob Storage
        return blob_client.upload_blob(job_criteria_json, "job_criteria.json")
    except ValueError as e:
        st.error(f"Azure Blob Storage configuration error: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return False


def main():
    st.title("📄 CV Analysis Tool")

    with st.sidebar:
        st.header("Upload CVs")

        # Multi-file uploader for CVs
        uploaded_files = st.file_uploader(
            "Upload CV files (PDF, DOCX, TXT)",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="cv_files"
        )

        # Job Criteria Configuration Section
        st.markdown("### ⚙️ Job Criteria Configuration")
        st.markdown("""
        **Update Job Criteria**
        
        Upload a job description document to update the criteria used for evaluating CVs.
        """)

        job_criteria_file = st.file_uploader(
            "Upload Job Criteria Document (PDF, DOCX)",
            type=["pdf", "docx"],
            key="job_criteria_file"
        )

        if job_criteria_file:
            # Extract text from the uploaded file
            job_text = extract_text_from_file(job_criteria_file)

            # Setup tabs for previewing content
            preview_tabs = st.tabs(["Extracted Text", "Generated JSON"])

            with preview_tabs[0]:
                st.text_area("Extracted Text from Document",
                             job_text, height=200)

            # Convert to JSON
            job_criteria = convert_text_to_job_criteria_json(job_text)

            with preview_tabs[1]:
                st.json(job_criteria)

            # Update button
            if st.button("Update Job Criteria", key="update_criteria"):
                with st.spinner("Updating job criteria..."):
                    if update_job_criteria_in_azure(job_criteria):
                        st.success("Job criteria updated successfully!")
                    else:
                        st.error(
                            "Failed to update job criteria. Check logs for details.")

        st.markdown("---")

        # Note about the application
        st.subheader("About This Application")
        st.text(
            "This application analyzes CVs using a sophisticated AI model. "
            "Upload your CVs to receive a detailed evaluation, including skills assessment, "
            "experience analysis, and overall match score."
        )

        # Note about criteria
        st.subheader("Evaluation Criteria")
        st.text(
            "This application uses a predefined set of evaluation criteria "
            "configured in the API. You can update these criteria by uploading "
            "a job description document in the Job Criteria Configuration section."
        )

        # Process button
        process_button = st.button("Analyze CVs", type="primary")

        # Export results button
        if st.session_state.get('analysis_completed'):
            export_results = st.download_button(
                label="Export Results as CSV",
                data=pd.DataFrame(st.session_state.get(
                    'results', [])).to_csv(index=False),
                file_name="cv_analysis_results.csv",
                mime="text/csv"
            )

    # Main content area
    if not uploaded_files:
        st.info(
            "Please upload one or more CV files from the sidebar to begin analysis.")

        # Show example
        with st.expander("View Example Analysis"):
            st.markdown("""
            ### Example CV Analysis Result
            
            #### Evaluation Report

            ### Overall Summary:
            John Smith's qualifications and extensive experience in software development make him a strong candidate for positions related to web development. His demonstrated expertise in Python, JavaScript, and React highlights his suitability for roles requiring these technical skills.

            ### Detailed Evaluation:

            #### Technical Skills
            John has strong experience with Python, JavaScript, and React, which are key requirements for the role. His background includes building RESTful APIs using Flask and implementing front-end features with JavaScript.

            #### Experience
            John has 7 years of experience in software development, exceeding the minimum requirement of 3 years. He has held senior positions and led a team of junior developers.

            #### Education
            John holds a Bachelor's degree in Computer Science from the University of Technology, meeting the educational requirement for the position.

            #### Communication Skills
            John's CV is well-written with clear descriptions of his responsibilities and achievements, indicating good written communication skills.

            ### Scoring:

            | Criteria | Score (1-5) | Comment |
            |---------------------------|-------------|---------|
            | Technical Skills | 5 | Strong experience in all required technologies. |
            | Experience | 5 | Exceeds required years of experience and has leadership experience. |
            | Education | 5 | Holds relevant degree in Computer Science. |
            | Communication Skills | 4 | Well-written CV demonstrates good communication ability. |

            ### Recommendation:
            John Smith is highly suitable for the position with a strong technical background, relevant experience, and appropriate education. His profile indicates he would be a valuable addition to the team.
            """)

    elif process_button or st.session_state.get('analysis_completed'):
        # Initialize session state
        if 'analysis_completed' not in st.session_state:
            st.session_state['analysis_completed'] = False
            st.session_state['results'] = []
            st.session_state['thread_ids'] = []

        # Process CVs
        if not st.session_state['analysis_completed'] and process_button:
            results = []
            thread_ids = []

            with st.spinner("Analyzing CVs..."):
                progress_bar = st.progress(0)

                for i, uploaded_file in enumerate(uploaded_files):
                    # Update progress
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)

                    # Extract text
                    cv_text = extract_text_from_file(uploaded_file)

                    # Send to API
                    identifier = f"cv_{i+1}"
                    response = APIClient.create_chat(
                        cv_text, identifier=identifier)

                    # Log the response for debugging if needed
                    if "error" in response:
                        st.error(
                            f"Error analyzing {uploaded_file.name}: {response['error']}")
                        continue

                    # Store result
                    result = {
                        "CV Name": uploaded_file.name,
                        "Analysis": response.get("agent_response", "Analysis failed"),
                        "Thread ID": response.get("thread_id", ""),
                        "Message ID": response.get("message_id", "")
                    }
                    results.append(result)
                    thread_ids.append(response.get("thread_id", ""))

                    # Simulate API delay to not overwhelm the server
                    time.sleep(0.5)

            st.session_state['results'] = results
            st.session_state['thread_ids'] = thread_ids
            st.session_state['analysis_completed'] = True

        # Display results
        st.header("Analysis Results")

        results = st.session_state.get('results', [])

        # Create tabs for each CV
        if results:
            tabs = st.tabs([result["CV Name"] for result in results])

            for i, tab in enumerate(tabs):
                with tab:
                    result = results[i]

                    # CV name and metadata
                    st.subheader(f"CV: {result['CV Name']}")

                    # Analysis result
                    st.markdown("### Analysis")

                    import json

                    for header in json.loads(result["Analysis"]):
                        if header.get('__dict__').get('chat_name') in ["summary", "applicant_lookup_agent"]:
                            st.markdown(header.get('__dict__').get('chat_response').get(
                                'chat_message').get('__dict__').get('content'))

                    # Feedback buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("👍 Helpful", key=f"helpful_{i}"):
                            feedback = APIClient.submit_feedback(
                                result["Message ID"],
                                result["Thread ID"],
                                True
                            )
                            st.success("Thank you for your feedback!")

                    with col2:
                        if st.button("👎 Not Helpful", key=f"not_helpful_{i}"):
                            feedback = APIClient.submit_feedback(
                                result["Message ID"],
                                result["Thread ID"],
                                False
                            )
                            st.success(
                                "Thank you for your feedback. We'll improve our analysis.")

            # Add a clear results button
            if st.button("Clear Results", type="secondary"):
                st.session_state['analysis_completed'] = False
                st.session_state['results'] = []
                st.session_state['thread_ids'] = []
                st.rerun()


if __name__ == "__main__":
    main()
