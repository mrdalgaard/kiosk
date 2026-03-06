function getContext() {
    const customerIdInput = document.getElementById('customer_id');
    const pinInput = document.getElementById('pin');
    
    if (customerIdInput) {
        return {
            input: customerIdInput,
            display: document.getElementById('pin-display'),
            form: document.getElementById('login-form'),
            isPassword: false
        };
    } else if (pinInput) {
        return {
            input: pinInput,
            display: document.getElementById('pin-display'),
            form: document.getElementById('admin-login-form'),
            isPassword: true
        };
    }
    return null;
}

window.updatePin = function(digit) {
    const ctx = getContext();
    if (!ctx) return;
    
    ctx.input.value += digit;
    if (ctx.display) {
        ctx.display.innerText = ctx.isPassword ? '●'.repeat(ctx.input.value.length) : ctx.input.value;
    }
};

window.clearPin = function() {
    const ctx = getContext();
    if (!ctx) return;
    
    ctx.input.value = '';
    if (ctx.display) {
        ctx.display.innerText = '';
    }
};

window.submitForm = function() {
    const ctx = getContext();
    if (ctx && ctx.form) {
        ctx.form.submit();
    } else {
        // Fallback
        const form = document.querySelector('form');
        if (form) form.submit();
    }
};

// Handle keyboard input
document.addEventListener('keydown', function (e) {
    const ctx = getContext();
    if (!ctx) return; // Only process if we are on a page with a keypad

    if (e.key >= '0' && e.key <= '9') {
        window.updatePin(e.key);
    } else if (e.key === 'Backspace') {
        ctx.input.value = ctx.input.value.slice(0, -1);
        if (ctx.display) {
            ctx.display.innerText = ctx.isPassword ? '●'.repeat(ctx.input.value.length) : ctx.input.value;
        }
    } else if (e.key === 'Enter') {
        if (ctx.form) ctx.form.submit();
    }
});

// Auto-trigger the keyboard/focus on load after initialization
function triggerBtnClick() {
    const ctx = getContext();
    if (ctx && ctx.input) {
        ctx.input.click();
        ctx.input.focus();
    }
}

// Auto-refresh page if idle for 5 minutes
let idleTime = 0;
const resetTimer = () => { idleTime = 0; };

document.addEventListener('mousemove', resetTimer);
document.addEventListener('keypress', resetTimer);
document.addEventListener('touchstart', resetTimer);
document.addEventListener('click', resetTimer);

setInterval(function () {
  idleTime++;
  if (idleTime >= 5) { // 5 minutes
    window.location.reload();
  }
}, 60000); // Check every minute

triggerBtnClick();
