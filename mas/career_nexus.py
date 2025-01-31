import streamlit as st
from pathlib import Path
import os
from src.mas.crew import Mas
from src.mas.S3 import upload_files_to_s3
import fitz 
import io
import time
from ragS3 import RAGS3
from dotenv import load_dotenv

load_dotenv()

def read_log_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return "Log file not found."
    except Exception as e:
        return f"Error reading log file: {str(e)}"

def convert_pdf_to_text(pdf_file):
    """
    Convert PDF file to text using PyMuPDF while preserving formatting and content.
    Args:
        pdf_file: Uploaded PDF file from Streamlit
    Returns:
        str: Extracted text from PDF
    """
    try:
        pdf_bytes = pdf_file.getvalue()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        text_content = []

        for page in doc:
            text = page.get_text("text") 
            if text.strip():
                text_content.append(text)

        doc.close()

        full_text = '\n\n'.join(text_content)

        if not full_text.strip():
            raise ValueError("No text could be extracted from the PDF")
            
        return full_text
        
    except Exception as e:
        raise Exception(f"Error converting PDF to text: {str(e)}")

# Ensure correct working directory
CURRENT_DIR = Path(os.getcwd())

# Define directories with absolute paths
BASE_DIR = CURRENT_DIR / ""
TEXT_FILES_DIR = BASE_DIR / "processed_resumes"
MD_FILES_DIR = BASE_DIR / "output"

# Ensure required directories exist
TEXT_FILES_DIR.mkdir(parents=True, exist_ok=True)
MD_FILES_DIR.mkdir(parents=True, exist_ok=True)

# Initialize session state variables
if "career_goal" not in st.session_state:
    st.session_state["career_goal"] = ""
if "resume_txt_path" not in st.session_state:
    st.session_state["resume_txt_path"] = ""
if "processing_done" not in st.session_state:
    st.session_state["processing_done"] = False
if "rag_initialized" not in st.session_state:
    st.session_state["rag_initialized"] = False
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "rag_instance" not in st.session_state:
    st.session_state["rag_instance"] = None

def initialize_rag():
    try:
        with st.spinner("Initializing RAG system..."):
            rag = RAGS3(
                bucket_name=os.environ.get("BUCKET_NAME"),
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
            )
            st.session_state["rag_instance"] = rag
            st.session_state["rag_initialized"] = True
            return True
    except Exception as e:
        st.error(f"Error initializing RAG system: {str(e)}")
        return False

# Streamlit UI
st.title("Career Nexus Prototype")
st.sidebar.title("Navigation")

# Resume upload
uploaded_resume = st.file_uploader("Upload Your Resume (.pdf)", type="pdf")

# Process only if both career goal and resume are present
if uploaded_resume and st.session_state["topic"] and not st.session_state["processing_done"]:
    try:
        # Convert PDF to text
        resume_text = convert_pdf_to_text(uploaded_resume)
        
        # Save converted text to file
        resume_path = TEXT_FILES_DIR / f"{uploaded_resume.name[:-4]}.txt"
        with open(resume_path, "w", encoding='utf-8') as txt_file:
            txt_file.write(resume_text)

        st.session_state["resume_txt_path"] = str(resume_path)
        st.success("Resume converted and uploaded successfully! Processing...")

        # Prepare inputs for Mas
        inputs = {
            "resume": str(resume_path),
            "topic": st.session_state["topic"]
        }

        try:
            Mas().crew().kickoff(inputs=inputs)
            upload_files_to_s3('output', os.environ.get('BUCKET_NAME'))
            st.session_state["processing_done"] = True
            st.success("Processing completed! Reports are ready.")
            st.rerun()
        except Exception as e:
            st.error(f"Error during processing: {str(e)}")
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        
elif uploaded_resume and not st.session_state["topic"]:
    st.warning("Please enter your career goal before uploading your resume.")

# Define categories based on generated markdown files
categories = {
    "Career Guidance": "Career Guidance.md",
    "Market Analysis": "Market Analysis.md",
    "Your Profile Assessment": "Profile Assessment.md",
    "Skill Evaluation": "Skill Evaluation.md",
    "Bias Mitigation": "Bias Mitigated Responses.md"
}

# Sidebar for selecting generated insights
nav_options = list(categories.keys()) + ["Chat with Career Advisor"]
selected_category = st.sidebar.selectbox("Select a category:", nav_options)

if selected_category != "Chat with Career Advisor":
    st.chat_message("assistant").write("What do you want to become?")
    career_goal = st.chat_input("Enter your career goal here...")
    if career_goal:
        st.session_state["topic"] = career_goal
        st.chat_message("user").write(career_goal)
        st.write(f"Your career goal: {career_goal}")

if selected_category == "Chat with Career Advisor":
    st.subheader("Chat with Your Career Advisor")
    
    if not st.session_state["processing_done"]:
        st.warning("Please complete the resume processing first to chat with the career advisor.")
    else:
        # Ensure RAG is initialized
        if not st.session_state["rag_initialized"]:
            if not initialize_rag():
                st.error("Unable to initialize the chat system. Please try again.")
                st.stop()
        
        # Display chat history
        for message in st.session_state["chat_history"]:
            role = message["role"]
            content = message["content"]
            with st.chat_message(role):
                st.write(content)

        # Chat input
        user_question = st.chat_input("Ask your career-related questions...")
        
        if user_question:
            # Display user message
            with st.chat_message("user"):
                st.write(user_question)

            # Get RAG response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        if st.session_state["rag_instance"] is None:
                            raise Exception("Chat system not properly initialized")
                            
                        response = st.session_state["rag_instance"].query(
                            user_question, 
                            st.session_state["chat_history"]
                        )
                        st.write(response["answer"])

                        # Update chat history
                        st.session_state["chat_history"].append({"role": "user", "content": user_question})
                        st.session_state["chat_history"].append({"role": "assistant", "content": response["answer"]})
                    except Exception as e:
                        st.error(f"Error getting response: {str(e)}")

# Display content only if processing is done
if st.session_state["processing_done"] and selected_category in categories:
    file_path = MD_FILES_DIR / categories[selected_category]
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as file:
            st.markdown(file.read(), unsafe_allow_html=True)  # Render Markdown
    else:
        st.warning(f"Report for '{selected_category}' is not available yet. Please wait for processing.")

# Styling for better UI
st.markdown(
    """
    <style>
    /* Title and upload button styling */
    .css-10trblm {
        text-align: center;
        font-size: 2rem;
        color: white;
    }

    /* Sidebar styling */
    .css-1lcbmhc {
        background-color: #2c2f33;
        padding: 20px;
        border-radius: 10px;
        color: white;
    }

    /* Markdown container styling */
    .markdown-text-container {
        background-color: #1c1e21;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
    }

    /* Center layout for the main content */
    .main {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True,)