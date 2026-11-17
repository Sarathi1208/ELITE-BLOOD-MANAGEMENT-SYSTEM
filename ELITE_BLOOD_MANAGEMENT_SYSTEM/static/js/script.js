(() => {
  const toggle = document.getElementById('menuToggle');
  const nav = document.getElementById('mainNav');
  if (toggle && nav) toggle.addEventListener('click', () => nav.classList.toggle('open'));

  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
      }
    });
  });

  const password = document.querySelector('input[name="password"]');
  const confirm = document.querySelector('input[name="confirm_password"]');
  if (password && confirm) {
    confirm.addEventListener('input', () => {
      confirm.setCustomValidity(confirm.value && confirm.value !== password.value ? 'Passwords do not match.' : '');
    });
    password.addEventListener('input', () => {
      confirm.setCustomValidity(confirm.value && confirm.value !== password.value ? 'Passwords do not match.' : '');
    });
  }
})();
