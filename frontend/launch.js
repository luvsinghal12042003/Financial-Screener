/**
 * Equity Finance Screener - Launch Access Page Interactivity
 */

document.addEventListener("DOMContentLoaded", () => {
    const emailForm = document.getElementById("email-form");
    const emailInput = document.getElementById("email-input");
    const submitBtn = document.getElementById("submit-btn");
    const btnText = document.getElementById("btn-text");
    const btnSpinner = document.getElementById("btn-spinner");
    const btnArrow = document.getElementById("btn-arrow");

    const errorAlert = document.getElementById("error-alert");
    const errorMessage = document.getElementById("error-message");

    const successCard = document.getElementById("success-card");
    const successEmailDisplay = document.getElementById("success-email-display");
    const deliveryModeBadge = document.getElementById("delivery-mode-badge");
    const portalLinkUrl = document.getElementById("portal-link-url");
    const directLaunchLink = document.getElementById("direct-launch-link");
    const copyLinkBtn = document.getElementById("copy-link-btn");
    const copyBtnText = document.getElementById("copy-btn-text");

    const previewEmailBtn = document.getElementById("preview-email-btn");
    const emailPreviewModal = document.getElementById("email-preview-modal");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const modalToEmail = document.getElementById("modal-to-email");
    const modalMockLaunchBtn = document.getElementById("modal-mock-launch-btn");

    let currentPortalLink = "/";

    function showError(msg) {
        if (errorMessage) errorMessage.textContent = msg;
        if (errorAlert) errorAlert.style.display = "flex";
    }

    function hideError() {
        if (errorAlert) errorAlert.style.display = "none";
    }

    function setLoading(isLoading) {
        if (submitBtn) submitBtn.disabled = isLoading;
        if (emailInput) emailInput.disabled = isLoading;
        if (btnSpinner) btnSpinner.style.display = isLoading ? "inline-block" : "none";
        if (btnArrow) btnArrow.style.display = isLoading ? "none" : "inline-block";
        if (btnText) btnText.textContent = isLoading ? "Generating Access Link..." : "Email Me Portal Link";
    }

    // Form Submission
    if (emailForm) {
        emailForm.addEventListener("submit", async e => {
            e.preventDefault();
            hideError();

            const email = (emailInput ? emailInput.value : "").trim();
            if (!email) {
                showError("Please enter your email address.");
                return;
            }

            // Client-side regex verification
            const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            if (!emailPattern.test(email)) {
                showError("Please enter a valid email address (e.g. name@domain.com).");
                return;
            }

            setLoading(true);

            try {
                const response = await fetch("/api/send-portal-link", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ email: email })
                });

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || "Failed to dispatch portal link. Please try again.");
                }

                const result = await response.json();
                currentPortalLink = result.portal_link || "/";

                // Populate Success State
                if (successEmailDisplay) successEmailDisplay.textContent = result.email || email;
                if (portalLinkUrl) portalLinkUrl.textContent = currentPortalLink;
                if (directLaunchLink) directLaunchLink.href = currentPortalLink;
                if (modalMockLaunchBtn) modalMockLaunchBtn.href = currentPortalLink;
                if (modalToEmail) modalToEmail.textContent = result.email || email;

                if (deliveryModeBadge) {
                    if (result.delivery_mode === "smtp") {
                        deliveryModeBadge.className = "delivery-badge smtp";
                        deliveryModeBadge.textContent = "Live SMTP Dispatched";
                    } else {
                        deliveryModeBadge.className = "delivery-badge simulated";
                        deliveryModeBadge.textContent = "Instant Demo Access";
                    }
                }

                if (successCard) {
                    successCard.style.display = "flex";
                    successCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
                }

                // Reset input
                if (emailInput) emailInput.value = "";
            } catch (err) {
                console.error("Submission error:", err);
                showError(err.message);
            } finally {
                setLoading(false);
            }
        });
    }

    // Copy Link Action
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener("click", async () => {
            if (!currentPortalLink) return;

            try {
                await navigator.clipboard.writeText(currentPortalLink);
                if (copyBtnText) copyBtnText.textContent = "Copied! ✓";
                copyLinkBtn.classList.add("btn-success");
                copyLinkBtn.classList.remove("btn-outline");

                setTimeout(() => {
                    if (copyBtnText) copyBtnText.textContent = "Copy Link";
                    copyLinkBtn.classList.remove("btn-success");
                    copyLinkBtn.classList.add("btn-outline");
                }, 2200);
            } catch (err) {
                // Fallback for clipboard
                const tempInput = document.createElement("input");
                tempInput.value = currentPortalLink;
                document.body.appendChild(tempInput);
                tempInput.select();
                document.execCommand("copy");
                document.body.removeChild(tempInput);

                if (copyBtnText) copyBtnText.textContent = "Copied! ✓";
                setTimeout(() => {
                    if (copyBtnText) copyBtnText.textContent = "Copy Link";
                }, 2200);
            }
        });
    }

    // Modal Events
    if (previewEmailBtn && emailPreviewModal) {
        previewEmailBtn.addEventListener("click", () => {
            emailPreviewModal.style.display = "flex";
        });
    }

    if (closeModalBtn && emailPreviewModal) {
        closeModalBtn.addEventListener("click", () => {
            emailPreviewModal.style.display = "none";
        });
    }

    if (emailPreviewModal) {
        emailPreviewModal.addEventListener("click", e => {
            if (e.target === emailPreviewModal) {
                emailPreviewModal.style.display = "none";
            }
        });
    }

    document.addEventListener("keydown", e => {
        if (e.key === "Escape" && emailPreviewModal && emailPreviewModal.style.display === "flex") {
            emailPreviewModal.style.display = "none";
        }
    });
});
