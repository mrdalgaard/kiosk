// Auto-trigger the keyboard/focus on load after initialization

function triggerBtnClick() {
  const customerIdInput = document.getElementById('customer_id');
  if (customerIdInput) {
    customerIdInput.click();
  } else {
    // If we're on the admin login page, try 'pin'
    const pinInput = document.getElementById('pin');
    if (pinInput) pinInput.click();
  }
}


function submit() {
  const submitBtn = document.getElementById("submit");
  if (submitBtn) {
    submitBtn.click();
  } else {
    // Fallback for admin login or other forms without ID 'submit'
    const form = document.querySelector('form');
    if (form) form.submit();
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
