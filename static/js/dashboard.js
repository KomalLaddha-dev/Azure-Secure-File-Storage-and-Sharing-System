/**
 * Azure Secure File Storage and Sharing System
 * Client-Side Application Controller
 * Handles drag-and-drop uploads, XHR progress, live search/filtering,
 * table/grid switching, health checks, and delete confirmation modals.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Application State
    let currentFiles = [];
    let currentFilter = "all";
    let currentSearch = "";
    let currentSort = "date-desc";
    let currentView = localStorage.getItem("preferredView") || "table";
    let fileToDelete = null;

    // DOM Elements
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const uploadProgress = document.getElementById("uploadProgress");
    const progressBar = document.getElementById("progressBar");
    const progressPercent = document.getElementById("progressPercent");
    const uploadFilename = document.getElementById("uploadFilename");

    const searchInput = document.getElementById("searchInput");
    const sortSelect = document.getElementById("sortSelect");
    const filterPills = document.querySelectorAll(".filter-pill");

    const tableViewBtn = document.getElementById("tableViewBtn");
    const gridViewBtn = document.getElementById("gridViewBtn");
    const fileTableView = document.getElementById("fileTableView");
    const fileGridView = document.getElementById("fileGridView");
    const fileTableBody = document.getElementById("fileTableBody");
    const fileGridBody = document.getElementById("fileGridBody");
    const emptyState = document.getElementById("emptyState");

    // KPI Metric Elements
    const totalFilesEl = document.getElementById("statTotalFiles");
    const storageUsedEl = document.getElementById("statStorageUsed");
    const storageProgressFill = document.getElementById("storageProgressFill");
    const storageQuotaText = document.getElementById("storageQuotaText");

    // Health & Architecture Elements
    const healthBadge = document.getElementById("healthBadge");
    const pulseDot = document.getElementById("pulseDot");
    const healthStatusText = document.getElementById("healthStatusText");

    // Modals
    const deleteModal = document.getElementById("deleteModal");
    const deleteFileNameSpan = document.getElementById("deleteFileName");
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
    const cancelDeleteBtn = document.getElementById("cancelDeleteBtn");
    const closeDeleteModalBtn = document.getElementById("closeDeleteModalBtn");

    const previewModal = document.getElementById("previewModal");
    const previewModalTitle = document.getElementById("previewModalTitle");
    const previewContainer = document.getElementById("previewContainer");
    const closePreviewModalBtn = document.getElementById("closePreviewModalBtn");

    const archModal = document.getElementById("archModal");
    const viewArchBtn = document.getElementById("viewArchBtn");
    const closeArchModalBtn = document.getElementById("closeArchModalBtn");

    const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
    const appSidebar = document.getElementById("appSidebar");
    const toastContainer = document.getElementById("toastContainer");

    // Max upload size in bytes (from window.MAX_SIZE_MB or fallback 25MB)
    const MAX_SIZE_BYTES = (window.APP_CONFIG?.maxSizeMb || 25) * 1024 * 1024;


    // =========================================================================
    // Toast Notification System
    // =========================================================================

    function showToast(title, message, type = "info") {
        if (!toastContainer) return;

        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let iconSvg = '';
        if (type === "success") {
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`;
        } else if (type === "danger") {
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
        } else {
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0078D4" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
        }

        toast.innerHTML = `
            <div class="toast-icon">${iconSvg}</div>
            <div class="toast-content">
                <div class="toast-title">${escapeHtml(title)}</div>
                <div class="toast-message">${escapeHtml(message)}</div>
            </div>
        `;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }


    // =========================================================================
    // Health Check & Cloud Monitoring
    // =========================================================================

    async function checkAzureHealth() {
        try {
            const res = await fetch("/health");
            const data = await res.json();
            
            if (data.storage && data.storage.connected) {
                pulseDot.className = "pulse-dot connected";
                healthStatusText.textContent = "Azure Connected";
                healthBadge.title = `Storage Account: ${data.storage.account_name} | Container: ${data.storage.container}`;
            } else {
                pulseDot.className = "pulse-dot error";
                healthStatusText.textContent = data.storage?.status === "unconfigured" ? "Azure Not Configured" : "Azure Disconnected";
                healthBadge.title = data.storage?.message || "Storage disconnected";
            }
        } catch (err) {
            pulseDot.className = "pulse-dot error";
            healthStatusText.textContent = "Azure Offline";
            healthBadge.title = "Failed to communicate with health probe endpoint";
        }
    }


    // =========================================================================
    // File Fetching & Listing
    // =========================================================================

    async function fetchFiles() {
        try {
            const res = await fetch("/api/files");
            const data = await res.json();

            if (data.success) {
                currentFiles = data.files || [];
                updateStats(data.total_count, data.total_bytes, data.total_bytes_formatted);
                renderFiles();
            } else {
                if (data.storage_configured === false) {
                    showToast("Azure Setup Required", "Configure AZURE_STORAGE_CONNECTION_STRING in your .env file.", "warning");
                } else {
                    showToast("Error", data.error || "Failed to load files", "danger");
                }
                currentFiles = [];
                renderFiles();
            }
        } catch (err) {
            showToast("Network Error", "Unable to fetch files from server", "danger");
        }
    }

    function updateStats(count, bytes, bytesFormatted) {
        if (totalFilesEl) totalFilesEl.textContent = count;
        if (storageUsedEl) storageUsedEl.textContent = bytesFormatted || "0 B";

        // Demo quota: 100 MB free tier demonstration quota
        const quotaBytes = 100 * 1024 * 1024;
        const usedPercent = Math.min(Math.round((bytes / quotaBytes) * 100), 100);

        if (storageProgressFill) {
            storageProgressFill.style.width = `${usedPercent}%`;
            if (usedPercent > 85) {
                storageProgressFill.style.background = "#EF4444";
            } else {
                storageProgressFill.style.background = "linear-gradient(90deg, var(--azure-blue), var(--azure-accent))";
            }
        }

        if (storageQuotaText) {
            storageQuotaText.textContent = `${usedPercent}% of 100 MB demo quota used`;
        }
    }


    // =========================================================================
    // Filtering, Search & Sorting
    // =========================================================================

    function getFilteredFiles() {
        let result = [...currentFiles];

        // 1. Category Filter
        if (currentFilter !== "all") {
            result = result.filter(file => file.category === currentFilter);
        }

        // 2. Search Query
        if (currentSearch.trim()) {
            const query = currentSearch.toLowerCase().trim();
            result = result.filter(file => file.filename.toLowerCase().includes(query));
        }

        // 3. Sort Order
        result.sort((a, b) => {
            if (currentSort === "date-desc") {
                return new Date(b.last_modified) - new Date(a.last_modified);
            } else if (currentSort === "date-asc") {
                return new Date(a.last_modified) - new Date(b.last_modified);
            } else if (currentSort === "name-asc") {
                return a.filename.localeCompare(b.filename);
            } else if (currentSort === "name-desc") {
                return b.filename.localeCompare(a.filename);
            } else if (currentSort === "size-desc") {
                return b.size - a.size;
            } else if (currentSort === "size-asc") {
                return a.size - b.size;
            }
            return 0;
        });

        return result;
    }

    function renderFiles() {
        const filtered = getFilteredFiles();

        if (filtered.length === 0) {
            fileTableView.style.display = "none";
            fileGridView.style.display = "none";
            emptyState.style.display = "block";
            return;
        }

        emptyState.style.display = "none";

        if (currentView === "table") {
            fileTableView.style.display = "block";
            fileGridView.style.display = "none";
            renderTableView(filtered);
        } else {
            fileTableView.style.display = "none";
            fileGridView.style.display = "block";
            renderGridView(filtered);
        }
    }

    function renderTableView(files) {
        fileTableBody.innerHTML = "";

        files.forEach(file => {
            const tr = document.createElement("tr");
            tr.className = "file-row";

            const iconSvg = getFileIconSvg(file.category);
            const dateStr = formatDate(file.last_modified);

            tr.innerHTML = `
                <td>
                    <div class="file-cell-name">
                        <div class="file-icon-box ${file.category}">${iconSvg}</div>
                        <div>
                            <div title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</div>
                            <div class="stat-subtext font-mono">${escapeHtml(file.content_type || 'binary')}</div>
                        </div>
                    </div>
                </td>
                <td><span class="pill-badge">${escapeHtml(file.category.toUpperCase())}</span></td>
                <td>${escapeHtml(file.size_formatted)}</td>
                <td>${escapeHtml(dateStr)}</td>
                <td>
                    <div class="file-actions">
                        ${canPreview(file.filename) ? `
                            <button class="action-btn" title="Preview File" onclick="window.previewFileAction('${escapeAttr(file.filename)}')">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            </button>
                        ` : ''}
                        <a href="/download/${encodeURIComponent(file.filename)}" class="action-btn" title="Download File">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        </a>
                        <button class="action-btn delete-btn" title="Delete File" onclick="window.openDeleteModal('${escapeAttr(file.filename)}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                </td>
            `;

            fileTableBody.appendChild(tr);
        });
    }

    function renderGridView(files) {
        fileGridBody.innerHTML = "";

        files.forEach(file => {
            const card = document.createElement("div");
            card.className = "grid-file-card";

            const iconSvg = getFileIconSvg(file.category);
            const dateStr = formatDate(file.last_modified);

            card.innerHTML = `
                <div>
                    <div class="grid-card-top">
                        <div class="file-icon-box ${file.category}">${iconSvg}</div>
                        <span class="pill-badge">${escapeHtml(file.extension.toUpperCase() || 'FILE')}</span>
                    </div>
                    <div class="grid-file-name" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</div>
                    <div class="grid-file-meta">
                        ${escapeHtml(file.size_formatted)} • ${escapeHtml(dateStr)}
                    </div>
                </div>
                <div class="grid-card-footer">
                    <span class="pill-badge">${escapeHtml(file.category)}</span>
                    <div class="file-actions">
                        ${canPreview(file.filename) ? `
                            <button class="action-btn btn-sm" title="Preview File" onclick="window.previewFileAction('${escapeAttr(file.filename)}')">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            </button>
                        ` : ''}
                        <a href="/download/${encodeURIComponent(file.filename)}" class="action-btn btn-sm" title="Download">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        </a>
                        <button class="action-btn delete-btn btn-sm" title="Delete" onclick="window.openDeleteModal('${escapeAttr(file.filename)}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                </div>
            `;

            fileGridBody.appendChild(card);
        });
    }


    // =========================================================================
    // File Upload with Drag & Drop + XHR Progress
    // =========================================================================

    if (dropzone && fileInput) {
        // Click to browse
        dropzone.addEventListener("click", () => fileInput.click());

        // File picker selection
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });

        // Drag & Drop events
        ["dragenter", "dragover"].forEach(evtName => {
            dropzone.addEventListener(evtName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add("drag-active");
            });
        });

        ["dragleave", "drop"].forEach(evtName => {
            dropzone.addEventListener(evtName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove("drag-active");
            });
        });

        dropzone.addEventListener("drop", (e) => {
            if (e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
    }

    function handleFileUpload(file) {
        if (!file) return;

        // Size validation
        if (file.size > MAX_SIZE_BYTES) {
            showToast("File Too Large", `File size exceeds the ${window.APP_CONFIG?.maxSizeMb || 25} MB limit.`, "danger");
            return;
        }

        if (file.size === 0) {
            showToast("Invalid File", "Cannot upload an empty (0 byte) file.", "danger");
            return;
        }

        // Show Progress Bar
        uploadFilename.textContent = file.name;
        progressBar.style.width = "0%";
        progressPercent.textContent = "0%";
        uploadProgress.style.display = "block";

        const formData = new FormData();
        formData.append("file", file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload", true);

        // Upload progress callback
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = `${percent}%`;
                progressPercent.textContent = `${percent}%`;
            }
        };

        xhr.onload = () => {
            if (xhr.status === 201 || xhr.status === 200) {
                progressBar.style.width = "100%";
                progressPercent.textContent = "100%";
                
                try {
                    const data = JSON.parse(xhr.responseText);
                    showToast("Upload Successful", data.message || `Uploaded ${file.name} to Azure Blob Storage`, "success");
                } catch {
                    showToast("Upload Successful", `Uploaded ${file.name}`, "success");
                }

                // Reset file input
                if (fileInput) fileInput.value = "";

                // Refresh files and hide progress after delay
                fetchFiles();
                setTimeout(() => {
                    uploadProgress.style.display = "none";
                }, 1200);
            } else {
                let errorMsg = "Upload failed";
                try {
                    const errData = JSON.parse(xhr.responseText);
                    errorMsg = errData.error || errData.message || errorMsg;
                } catch {}
                showToast("Upload Failed", errorMsg, "danger");
                uploadProgress.style.display = "none";
            }
        };

        xhr.onerror = () => {
            showToast("Network Error", "Storage upload interrupted. Check your internet connection.", "danger");
            uploadProgress.style.display = "none";
        };

        xhr.send(formData);
    }


    // =========================================================================
    // Delete File Modal & Execution
    // =========================================================================

    window.openDeleteModal = function(filename) {
        fileToDelete = filename;
        deleteFileNameSpan.textContent = filename;
        deleteModal.classList.add("show");
    };

    function closeDeleteModal() {
        deleteModal.classList.remove("show");
        fileToDelete = null;
    }

    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", closeDeleteModal);
    if (closeDeleteModalBtn) closeDeleteModalBtn.addEventListener("click", closeDeleteModal);

    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", async () => {
            if (!fileToDelete) return;

            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.textContent = "Deleting from Azure...";

            try {
                const res = await fetch(`/api/delete/${encodeURIComponent(fileToDelete)}`, {
                    method: "POST"
                });
                const data = await res.json();

                if (data.success) {
                    showToast("Deleted", data.message || `File deleted from Azure Storage`, "success");
                    closeDeleteModal();
                    fetchFiles();
                } else {
                    showToast("Delete Failed", data.error || "Unable to delete file", "danger");
                }
            } catch (err) {
                showToast("Error", "Failed to communicate with Azure storage endpoint", "danger");
            } finally {
                confirmDeleteBtn.disabled = false;
                confirmDeleteBtn.textContent = "Delete File";
            }
        });
    }


    // =========================================================================
    // File Preview Modal
    // =========================================================================

    function canPreview(filename) {
        const ext = filename.rsplit ? filename.rsplit(".", 1)[-1] : filename.split(".").pop().toLowerCase();
        return ["png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "txt", "md", "json", "py", "js"].includes(ext);
    }

    window.previewFileAction = function(filename) {
        const ext = filename.split(".").pop().toLowerCase();
        previewModalTitle.textContent = `Preview: ${filename}`;
        previewContainer.innerHTML = "";

        const previewUrl = `/preview/${encodeURIComponent(filename)}`;

        if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
            previewContainer.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <img src="${previewUrl}" alt="${escapeHtml(filename)}" style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: var(--shadow-md);">
                </div>
            `;
        } else if (ext === "pdf") {
            previewContainer.innerHTML = `
                <iframe src="${previewUrl}" style="width: 100%; height: 500px; border: 1px solid var(--border-color); border-radius: 8px;"></iframe>
            `;
        } else {
            // Text or code preview
            previewContainer.innerHTML = `<div style="padding: 20px; text-align: center;">Loading file content from Azure...</div>`;
            fetch(previewUrl)
                .then(r => r.text())
                .then(text => {
                    previewContainer.innerHTML = `
                        <pre style="background: #0F172A; color: #F8FAFC; padding: 18px; border-radius: 8px; overflow-x: auto; max-height: 480px; font-size: 0.85rem;"><code>${escapeHtml(text)}</code></pre>
                    `;
                })
                .catch(() => {
                    previewContainer.innerHTML = `<div style="color: var(--color-danger); padding: 20px;">Failed to preview text file content.</div>`;
                });
        }

        previewModal.classList.add("show");
    };

    if (closePreviewModalBtn) {
        closePreviewModalBtn.addEventListener("click", () => {
            previewModal.classList.remove("show");
            previewContainer.innerHTML = "";
        });
    }


    // =========================================================================
    // Architecture & College Evaluation Modal
    // =========================================================================

    if (viewArchBtn && archModal) {
        viewArchBtn.addEventListener("click", async () => {
            archModal.classList.add("show");
            try {
                const res = await fetch("/api/cloud-info");
                const info = await res.json();
                document.getElementById("archHosting").textContent = info.hosting;
                document.getElementById("archStorage").textContent = info.storage_tier;
                document.getElementById("archIsolation").textContent = info.isolation_pattern;
                document.getElementById("archServer").textContent = info.web_server;
            } catch {}
        });
    }

    if (closeArchModalBtn) {
        closeArchModalBtn.addEventListener("click", () => {
            archModal.classList.remove("show");
        });
    }


    // =========================================================================
    // UI Event Listeners (Search, Filter, View Switch, Sidebar)
    // =========================================================================

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            currentSearch = e.target.value;
            renderFiles();
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", (e) => {
            currentSort = e.target.value;
            renderFiles();
        });
    }

    filterPills.forEach(pill => {
        pill.addEventListener("click", () => {
            filterPills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentFilter = pill.dataset.filter || "all";
            renderFiles();
        });
    });

    if (tableViewBtn && gridViewBtn) {
        tableViewBtn.addEventListener("click", () => {
            currentView = "table";
            localStorage.setItem("preferredView", "table");
            tableViewBtn.classList.add("active");
            gridViewBtn.classList.remove("active");
            renderFiles();
        });

        gridViewBtn.addEventListener("click", () => {
            currentView = "grid";
            localStorage.setItem("preferredView", "grid");
            gridViewBtn.classList.add("active");
            tableViewBtn.classList.remove("active");
            renderFiles();
        });

        // Initialize button active state
        if (currentView === "grid") {
            gridViewBtn.classList.add("active");
            tableViewBtn.classList.remove("active");
        }
    }

    if (sidebarToggleBtn && appSidebar) {
        sidebarToggleBtn.addEventListener("click", () => {
            appSidebar.classList.toggle("open");
        });
    }

    // Close modals on clicking backdrop
    [deleteModal, previewModal, archModal].forEach(modal => {
        if (modal) {
            modal.addEventListener("click", (e) => {
                if (e.target === modal) {
                    modal.classList.remove("show");
                }
            });
        }
    });


    // =========================================================================
    // SVG Icons & Helper Functions
    // =========================================================================

    function getFileIconSvg(category) {
        switch (category) {
            case "document":
                return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`;
            case "image":
                return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
            case "archive":
                return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>`;
            case "code":
                return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
            default:
                return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>`;
        }
    }

    function formatDate(isoStr) {
        if (!isoStr) return "Just now";
        try {
            const d = new Date(isoStr);
            return d.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
            });
        } catch {
            return isoStr.substring(0, 10);
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeAttr(str) {
        return escapeHtml(str).replace(/"/g, "&quot;");
    }


    // =========================================================================
    // Initial Load & Health Poll
    // =========================================================================

    fetchFiles();
    checkAzureHealth();
    // Poll Azure Health status every 30 seconds
    setInterval(checkAzureHealth, 30000);
});
