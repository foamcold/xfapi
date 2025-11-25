
// 自定义模态框逻辑

// 注入模态框 HTML
const modalHTML = `
<div id="custom-modal-overlay" class="custom-modal-overlay">
    <div class="custom-modal">
        <div class="custom-modal-header" id="custom-modal-title"></div>
        <div class="custom-modal-body" id="custom-modal-message"></div>
        <div class="custom-modal-footer" id="custom-modal-footer">
            <!-- Buttons will be injected here -->
        </div>
    </div>
</div>
`;

document.body.insertAdjacentHTML('beforeend', modalHTML);

const modalOverlay = document.getElementById('custom-modal-overlay');
const modalTitle = document.getElementById('custom-modal-title');
const modalMessage = document.getElementById('custom-modal-message');
const modalFooter = document.getElementById('custom-modal-footer');

let resolveModal = null;

function showModal(title, message, type = 'alert') {
    return new Promise((resolve) => {
        resolveModal = resolve;
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalFooter.innerHTML = '';

        if (type === 'confirm') {
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'custom-modal-btn cancel';
            cancelBtn.textContent = '取消';
            cancelBtn.onclick = () => closeModal(false);
            modalFooter.appendChild(cancelBtn);

            const confirmBtn = document.createElement('button');
            confirmBtn.className = 'custom-modal-btn confirm';
            confirmBtn.textContent = '确定';
            confirmBtn.onclick = () => closeModal(true);
            modalFooter.appendChild(confirmBtn);
        } else {
            const okBtn = document.createElement('button');
            okBtn.className = 'custom-modal-btn confirm';
            okBtn.textContent = '确定';
            okBtn.onclick = () => closeModal(true);
            modalFooter.appendChild(okBtn);
        }

        modalOverlay.classList.add('active');
    });
}

function closeModal(result) {
    modalOverlay.classList.remove('active');
    if (resolveModal) {
        resolveModal(result);
        resolveModal = null;
    }
}

// 暴露全局函数
window.showAlert = (message, title = '提示') => showModal(title, message, 'alert');
window.showConfirm = (message, title = '确认') => showModal(title, message, 'confirm');
