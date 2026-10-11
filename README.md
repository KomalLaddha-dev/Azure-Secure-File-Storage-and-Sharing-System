# Azure Secure File Storage and Sharing System

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask)](https://flask.palletsprojects.com/)
[![Azure App Service](https://img.shields.io/badge/Azure-App%20Service%20(Linux)-0078D4?logo=microsoftazure)](https://azure.microsoft.com/en-us/products/app-service/)
[![Azure Blob Storage](https://img.shields.io/badge/Azure-Blob%20Storage-0078D4?logo=microsoftazure)](https://azure.microsoft.com/en-us/products/storage/blobs/)
[![Tests](https://img.shields.io/badge/Tests-25%20Passed-success?logo=pytest)](https://pytest.org/)

A secure, scalable, cloud-native file storage and sharing web application engineered for college Cloud Computing evaluation and enterprise cloud architectures. Deployed on **Microsoft Azure App Service (Linux)** with object storage powered by **Azure Blob Storage (SDK v12)** and a responsive, high-contrast dashboard.

---

## 📑 Table of Contents

1. [Project Overview & Objectives](#1-project-overview--objectives)
2. [Cloud Computing Concepts Demonstrated](#2-cloud-computing-concepts-demonstrated)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Project Structure](#5-project-structure)
6. [Security Architecture & Zero Key Leakage](#6-security-architecture--zero-key-leakage)
7. [Azure Resource Configuration Checklist](#7-azure-resource-configuration-checklist)
8. [Local Development Setup](#8-local-development-setup)
9. [Azure App Service Deployment Guide](#9-azure-app-service-deployment-guide)
10. [Automated Testing](#10-automated-testing)
11. [Troubleshooting & Common Deployment Errors](#11-troubleshooting--common-deployment-errors)
12. [College Evaluation & Viva Demonstration Script](#12-college-evaluation--viva-demonstration-script)

---

## 1. Project Overview & Objectives

In modern cloud computing, traditional filesystem-based file management on virtual machines lacks horizontal scalability, resiliency, and cost-efficiency. This project demonstrates how to decouple application compute from persistent object storage using cloud-native design principles.

### Key Objectives
* **Scalable Object Storage:** Store arbitrary binary objects (PDFs, images, code, archives) in Azure Blob Storage with automated metadata attribution.
* **Tenant Prefix Isolation:** Enforce multi-user boundaries where each user's assets are partitioned within isolated container prefixes (`<username>/<filename>`).
* **Zero Client-Side Key Exposure:** Direct storage access keys, SAS credentials, or private connection strings are never sent to the browser.
* **Production-Grade App Service Deployment:** Optimized for Azure App Service Linux using Gunicorn multi-worker WSGI server.
* **Live Health Monitoring:** Built-in `/health` diagnostic probe reporting cloud connectivity without leaking sensitive secrets.

---

## 2. Cloud Computing Concepts Demonstrated

This project is tailored to demonstrate key theoretical and practical competencies in University Cloud Computing curricula:

| Cloud Concept | Implementation in this Project |
| :--- | :--- |
| **PaaS (Platform as a Service)** | Azure App Service abstracts virtual machines, operating system patching, runtime management, and automated scaling. |
| **Object Storage vs. Block/File Storage** | Azure Blob Storage stores files as flat objects identified by key prefixes with rich metadata, offering 99.999999999% (11 nines) durability. |
| **Stateless Application Tier** | The Flask application does not store files or permanent state on local server disk, allowing horizontal scale-out to $N$ App Service instances. |
| **Shared Responsibility Model** | Azure manages physical infrastructure, virtualization, and storage hardware; the application layer handles access control, tenant isolation, and input validation. |
| **Multi-Tenancy via Key Partitioning** | Avoids creating expensive per-user containers by leveraging logical hierarchical naming: `container/<user_id>/<filename>`. |
| **Elasticity & Cost Optimization** | Blob Storage charges solely for actual bytes stored and transaction operations (Hot Tier) rather than over-provisioned disk capacity. |
| **Streaming Proxy Pattern** | Files are streamed via HTTP chunked transfer directly from Azure SDK to client, preventing server RAM exhaustion on large files. |

---

## 3. System Architecture

```
[ Client Browser / Mobile ]
            │  HTTPS (TLS 1.3)
            ▼
┌──────────────────────────────────────────────────────────┐
│ Microsoft Azure App Service (Linux PaaS)                 │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Gunicorn WSGI Server (2 Workers / 4 Threads)        │  │
│  │                                                    │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │ Python Flask Application (Stateless)          │  │  │
│  │  │                                              │  │  │
│  │  │  • Session Auth & HMAC Verification          │  │  │
│  │  │  • Werkzeug Path-Traversal Defense           │  │  │
│  │  │  • Extension Whitelist & Size Validation     │  │  │
│  │  │  • Health Probe (/health)                    │  │  │
│  │  └──────────────────┬───────────────────────────┘  │  │
│  └─────────────────────┼──────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────┘
                         │ Azure Storage Blob SDK v12
                         │ (Encrypted HTTPS via Connection String)
                         ▼
┌──────────────────────────────────────────────────────────┐
│ Microsoft Azure Blob Storage Account                     │
│ Container: 'secure-files-container' (Access: Private)    │
│                                                          │
│   ├── student/                                           │
│   │     ├── report_v1.pdf                                │
│   │     └── dataset.csv                                  │
│   ├── faculty/                                           │
│   │     └── syllabus.docx                                │
│   └── admin/                                             │
│         └── system_backup.zip                            │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

* **Backend Framework:** Python 3.10+ / Flask 3.1
* **Cloud Storage SDK:** `azure-storage-blob` (v12.30.0)
* **Application Gateway / WSGI:** Gunicorn 21.2+ (multi-worker, multithreaded)
* **Frontend Design System:** Semantic HTML5, Custom Responsive CSS (Azure Enterprise theme conforming to WCAG AA accessibility standards), Vanilla JavaScript ES6+
* **Authentication:** Cryptographic HTTP-Only session cookies with HMAC constant-time digest verification
* **Testing & Quality Assurance:** `pytest` (25 automated test cases with mocking)

---

## 5. Project Structure

```text
f:/CCLab/
├── app.py                  # Main Flask application and REST routes
├── azure_storage.py        # Modular Azure Blob Storage SDK service
├── auth.py                 # Authentication, decorators, and session handlers
├── config.py               # Environment configuration loader
├── requirements.txt        # Production dependency specifications
├── startup.txt             # Azure App Service Linux startup command
├── .env.example            # Environment configuration template
├── .gitignore              # Git exclusions for secrets and caches
├── README.md               # Comprehensive architectural & deployment guide
├── static/
│   ├── css/
│   │   └── style.css       # Azure Enterprise design system & responsive layout
│   └── js/
│       └── dashboard.js    # Drag-and-drop, XHR progress, live filters, modals
├── templates/
│   ├── base.html           # Base layout with SEO & accessibility tags
│   ├── login.html          # Polished sign-in with quick demo accounts
│   ├── dashboard.html      # Main cloud management dashboard
│   ├── 404.html            # Resource not found page
│   └── error.html          # Clean error template
└── tests/
    ├── __init__.py         # Test package marker
    ├── test_auth.py        # Authentication & authorization tests
    ├── test_validation.py  # Path traversal, extension & size tests
    ├── test_storage.py     # Azure Blob SDK mock tests
    └── test_routes.py      # Flask integration route tests
```

---

## 6. Security Architecture & Zero Key Leakage

1. **Server-Side Secret Isolation:**
   * The Azure connection string and storage account key reside strictly on the server (configured in Azure App Settings).
   * Web browsers never obtain connection strings or raw blob storage URLs.
2. **Private Container Enforcement:**
   * The Azure Storage container is provisioned with **Private (no anonymous read access)** access level. Direct public web URLs cannot download any stored blobs.
3. **Streamed Backend Proxying:**
   * File downloads and previews are authenticated through Flask routes (`/download/<filename>` and `/preview/<filename>`) and streamed using `download_blob().chunks()`.
4. **Path Traversal & Filename Sanitization:**
   * Filenames are strictly sanitized using `werkzeug.utils.secure_filename()` and regular expression filters to strip traversal patterns like `../../etc/passwd` or `..\windows\system32`.
5. **Multi-Tenant User Prefix Isolation:**
   * Every file is stored with key `<user_id>/<filename>`.
   * Listing queries strictly match `name_starts_with="<user_id>/"`.
   * User `student` cannot view, download, or delete files stored under `faculty/`.
6. **Session Security:**
   * `SESSION_COOKIE_HTTPONLY = True` (mitigates XSS cookie theft).
   * `SESSION_COOKIE_SAMESITE = 'Lax'` (mitigates CSRF vulnerabilities).
   * `SESSION_COOKIE_SECURE = True` in production environments (ensures cookies are only transmitted over TLS/HTTPS).

---

## 7. Azure Resource Configuration Checklist

Before deploying, ensure the following Azure resources are prepared in the [Azure Portal](https://portal.azure.com/):

- [ ] **1. Azure Resource Group:** Create a dedicated resource group (e.g., `rg-cclab-storage-eastus`).
- [ ] **2. Azure Storage Account:**
  - Performance: Standard
  - Redundancy: Locally-redundant storage (LRS) for cost efficiency
  - Primary service: Blob storage
- [ ] **3. Private Blob Container:**
  - Create a container named `secure-files-container` (or matching your `.env` setting).
  - Public access level: **Private (no anonymous access)**.
- [ ] **4. Retrieve Connection String:**
  - Navigate to: Storage Account $\rightarrow$ **Security + networking** $\rightarrow$ **Access keys**.
  - Copy **Connection string** from `key1`.
- [ ] **5. Azure App Service (Linux):**
  - Publish: Code
  - Runtime stack: Python 3.12 (or 3.11 / 3.10)
  - Operating System: Linux
  - Pricing Plan: Basic B1 or Free F1
- [ ] **6. App Service Configuration (Application Settings):**
  - Under App Service $\rightarrow$ **Settings** $\rightarrow$ **Environment variables**, set:
    * `AZURE_STORAGE_CONNECTION_STRING` = `[Your Connection String]`
    * `AZURE_STORAGE_CONTAINER_NAME` = `secure-files-container`
    * `SECRET_KEY` = `[Random Hex 64-char String]`
    * `FLASK_ENV` = `production`
    * `MAX_CONTENT_LENGTH_MB` = `25`
    * `APP_USERS` = `{"student":"azurepass123","faculty":"cloudpass456","admin":"adminpass789"}`
- [ ] **7. Startup Command:**
  - Under App Service $\rightarrow$ **Settings** $\rightarrow$ **Configuration** $\rightarrow$ **General settings**:
  - Set Startup Command: `gunicorn --bind=0.0.0.0:8000 --workers=2 --threads=4 --timeout=120 app:app` (or refer to `startup.txt`).

---

## 8. Local Development Setup

### Prerequisites
* Python 3.10, 3.11, or 3.12
* Git

### Step-by-Step Instructions

1. **Clone or Navigate to the Workspace:**
   ```bash
   cd project
   ```

2. **Create and Activate a Virtual Environment:**
   * On Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * On Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   * Copy the template:
     ```bash
     cp .env.example .env
     ```
   * Edit `.env` and fill in your Azure Storage connection string:
     ```env
     SECRET_KEY=college_cclab_secure_random_key_2026
     FLASK_ENV=development
     PORT=5000
     AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your_account;AccountKey=your_key==;EndpointSuffix=core.windows.net
     AZURE_STORAGE_CONTAINER_NAME=secure-files-container
     MAX_CONTENT_LENGTH_MB=25
     APP_USERS={"student": "azurepass123", "faculty": "cloudpass456", "admin": "adminpass789"}
     ```

5. **Start the Application:**
   ```bash
   python app.py
   ```
   Open your browser at `http://127.0.0.1:5000`.

---

## 9. Azure App Service Deployment Guide

### Method A: Deploy via Azure CLI (Recommended)

1. **Log in to Azure:**
   ```bash
   az login
   ```

2. **Create Resource Group and Storage Account:**
   ```bash
   az group create --name rg-cclab --location eastus
   
   az storage account create \
     --name cclabstorage$RANDOM \
     --resource-group rg-cclab \
     --location eastus \
     --sku Standard_LRS
   ```

3. **Retrieve Storage Connection String:**
   ```bash
   CONN_STR=$(az storage account show-connection-string \
     --name <YourStorageAccountName> \
     --resource-group rg-cclab \
     --query connectionString --output tsv)
   ```

4. **Create App Service Plan and Web App:**
   ```bash
   az appservice plan create \
     --name plan-cclab \
     --resource-group rg-cclab \
     --sku B1 \
     --is-linux

   az webapp create \
     --resource-group rg-cclab \
     --plan plan-cclab \
     --name azure-secure-files-$RANDOM \
     --runtime "PYTHON:3.12" \
     --startup-file "gunicorn --bind=0.0.0.0:8000 --workers=2 --threads=4 --timeout=120 app:app"
   ```

5. **Configure App Settings in App Service:**
   ```bash
   az webapp config appsettings set \
     --resource-group rg-cclab \
     --name <YourWebAppName> \
     --settings \
       AZURE_STORAGE_CONNECTION_STRING="$CONN_STR" \
       AZURE_STORAGE_CONTAINER_NAME="secure-files-container" \
       SECRET_KEY="$(openssl rand -hex 32)" \
       FLASK_ENV="production" \
       MAX_CONTENT_LENGTH_MB="25"
   ```

6. **Deploy Application Code via ZIP:**
   ```bash
   zip -r deploy.zip . -x "*.git*" ".venv/*" "__pycache__/*" ".pytest_cache/*"
   az webapp deploy --resource-group rg-cclab --name <YourWebAppName> --src-path deploy.zip
   ```

---

## 10. Automated Testing

The project includes 25 unit and integration tests covering authentication, route authorization, input sanitization, file size limits, extension whitelisting, and mocked Azure SDK operations.

Run the entire test suite:
```bash
python -m pytest -v
```

Expected Output:
```text
tests/test_auth.py::test_credential_verification_success PASSED          [  4%]
tests/test_auth.py::test_credential_verification_failure PASSED          [  8%]
tests/test_auth.py::test_login_flow PASSED                               [ 12%]
tests/test_auth.py::test_login_invalid_password PASSED                   [ 16%]
tests/test_auth.py::test_logout_flow PASSED                              [ 20%]
tests/test_auth.py::test_unauthenticated_access_redirection PASSED       [ 24%]
tests/test_auth.py::test_unauthenticated_api_access_denial PASSED        [ 28%]
tests/test_routes.py::test_health_endpoint PASSED                        [ 32%]
tests/test_routes.py::test_cloud_info_endpoint PASSED                    [ 36%]
tests/test_routes.py::test_api_upload_success PASSED                     [ 40%]
tests/test_routes.py::test_api_list_files PASSED                         [ 44%]
tests/test_routes.py::test_download_file_stream PASSED                   [ 48%]
tests/test_routes.py::test_api_delete_file PASSED                        [ 52%]
tests/test_storage.py::test_storage_service_unconfigured PASSED          [ 56%]
tests/test_storage.py::test_health_check_masks_credentials PASSED        [ 60%]
tests/test_storage.py::test_upload_file_enforces_user_prefix PASSED      [ 64%]
tests/test_storage.py::test_list_files_filters_by_user_prefix PASSED     [ 68%]
tests/test_storage.py::test_delete_file_user_isolation PASSED            [ 72%]
tests/test_validation.py::test_sanitize_filename_prevents_path_traversal PASSED [ 76%]
tests/test_validation.py::test_sanitize_filename_empty_handling PASSED   [ 80%]
tests/test_validation.py::test_format_file_size PASSED                   [ 84%]
tests/test_validation.py::test_categorize_file PASSED                    [ 88%]
tests/test_validation.py::test_reject_unsupported_file_extension PASSED  [ 92%]
tests/test_validation.py::test_reject_empty_zero_byte_file PASSED        [ 96%]
tests/test_validation.py::test_reject_oversized_file PASSED              [100%]

======================== 25 passed in 0.97s ========================
```

---

## 11. Troubleshooting & Common Deployment Errors

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| **App Service shows "Application Error" (HTTP 502 / 503)** | Missing startup command or gunicorn worker timeout. | Ensure App Service Startup Command is: `gunicorn --bind=0.0.0.0:8000 --workers=2 --threads=4 --timeout=120 app:app`. Check logs using `az webapp log tail`. |
| **Dashboard shows "Azure Offline" / Red Health Indicator** | `AZURE_STORAGE_CONNECTION_STRING` missing or incorrect. | Verify connection string in `.env` or App Service Application Settings. Ensure `EndpointSuffix=core.windows.net` is intact. |
| **Upload returns HTTP 403 Forbidden** | Storage account network firewall blocks requests or Access Key expired. | In Azure Portal $\rightarrow$ Storage Account $\rightarrow$ Networking, enable "Allow access from all networks" or configure App Service VNet integration. |
| **Upload returns HTTP 413 Payload Too Large** | File size exceeds configured `MAX_CONTENT_LENGTH_MB`. | Adjust `MAX_CONTENT_LENGTH_MB` in environment variables if larger uploads are required. |
| **Login fails on first attempt** | Bad credentials or missing `SECRET_KEY`. | Use one of the demo credentials (`student` / `azurepass123`). Ensure `SECRET_KEY` is defined. |

---

## 12. College Evaluation & Viva Demonstration Script

Follow this step-by-step walkthrough to present the project to university examiners or project evaluators:

### 🎙️ Phase 1: Problem Statement & Cloud Architecture Pitch (1 minute)
> *"Examiners, our project addresses a foundational challenge in modern Cloud Computing: decoupling compute from storage. In traditional on-premises setups, applications store user files on local server hard disks. If the server crashes or traffic surges, scaling is difficult and data can be lost.*
> 
> *Our solution implements a cloud-native architecture on Microsoft Azure. The Flask application runs statelessly on Azure App Service Linux, while persistent files are managed as scalable objects in Azure Blob Storage with automated multi-tenant isolation."*

### 🎙️ Phase 2: Live Demonstration Steps (3 minutes)

1. **Demonstrate Authentication & Session Security:**
   * Navigate to `/login`.
   * Explain the demo credential pills: click `student` to auto-fill credentials.
   * Highlight that the password is verified using timing-attack-safe HMAC comparison.
   * Sign in and observe redirection to the protected dashboard.

2. **Demonstrate Cloud Health Probe:**
   * Point to the top-right green pulsing badge: **Azure Connected**.
   * Open the `/health` endpoint in a new tab to show that the system returns JSON status with a masked account name, proving zero credential exposure.

3. **Demonstrate File Upload & Interactive Progress:**
   * Drag and drop a file (e.g., `project_report.pdf` or an image) into the dashed dropzone.
   * Point out the live percentage progress bar powered by asynchronous `XMLHttpRequest` upload events.
   * Notice the automatic categorization badge (e.g., `DOCUMENT`), file size calculation, and timestamp.

4. **Demonstrate Search, Filter, and Grid/Table Views:**
   * Type in the search box to show instant client-side filtering without reloading the page.
   * Click category filter pills: `Documents`, `Images`, `Code`.
   * Toggle between the dense **Table View** and the visual card **Grid View**.

5. **Demonstrate Secure Inline Preview & Download:**
   * Click the **Preview** eye icon on an uploaded image or PDF to inspect it inside the modal without exposing private Azure URLs.
   * Click the **Download** button to verify chunked streaming directly to the client browser.

6. **Demonstrate Multi-Tenant Storage Isolation (Crucial for Evaluation):**
   * Sign out of the `student` account.
   * Sign in as `faculty` (`cloudpass456`).
   * Observe that `faculty`'s dashboard is completely isolated—`student`'s files are not visible!
   * Explain: *"In Azure Blob Storage, files are partitioned under user prefixes: `student/*` vs `faculty/*`. Neither user can view, download, or delete the other's data."*

7. **Demonstrate Safe File Deletion:**
   * Click the trash icon on a file.
   * Show the confirmation modal displaying the target filename.
   * Confirm deletion and note the immediate recalculation of storage metrics.

8. **Review Cloud Architecture Modal:**
   * Click **Cloud Architecture** on the sidebar to review the built-in viva guide summarizing PaaS, Hot Tier Object Storage, and defense-in-depth principles.

---

## 👨‍💻 Authors & Academic Attribution

* **Project Name:** Azure Secure File Storage and Sharing System
* **Domain:** Cloud Computing Laboratory (CCLab)
* **Cloud Provider:** Microsoft Azure
* **License:** MIT License
