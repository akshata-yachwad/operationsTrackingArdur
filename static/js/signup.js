import { api } from './core/api.js';
import { toast } from './core/toast.js';

// Setup password visibility toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtns = document.querySelectorAll('.password-toggle');
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Find the closest input group and the input inside it
            const group = this.closest('.input-group');
            const input = group.querySelector('input');
            if (!input) return;
            
            const isPwd = input.type === 'password';
            input.type = isPwd ? 'text' : 'password';
            const icon = this.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye', !isPwd);
                icon.classList.toggle('fa-eye-slash', isPwd);
            }
        });
    });
});

document.getElementById('emp_id').addEventListener('blur', async function () {
    const empId = this.value;
    if (!empId) return;

    try {
        const data = await api.post('/auth/check-employee/', { emp_id: empId });
        // Depending on what check-employee returns, either data.name or data.data.name
        const name = data?.name || (data?.data && data.data.name);
        
        if (name) {
            document.getElementById('name').value = name;
            document.getElementById('name').classList.remove('error');
        } else {
            document.getElementById('name').value = '';
            toast.error('Employee ID not found');
        }
    } catch (error) {
        console.error('Check employee error:', error);
        document.getElementById('name').value = '';
        toast.error(error.message || 'An error occurred while checking the employee ID.');
    }
});

document.getElementById('signup-form').addEventListener('submit', async function (event) {
    event.preventDefault();

    const empId = document.getElementById('emp_id').value;
    const name = document.getElementById('name').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;

    if (!empId || !name || !password) {
        toast.error('All fields are required');
        return;
    }

    if (password.length < 8) {
        toast.error('Password must be at least 8 characters long');
        return;
    }

    if (password !== confirmPassword) {
        toast.error('Passwords do not match');
        return;
    }

    const submitBtn = this.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing Up...';
    submitBtn.disabled = true;

    try {
        await api.post('/auth/signup/', { emp_id: empId, name: name, password: password });
        toast.success('Registration successful! Redirecting to login...');
        
        setTimeout(() => {
            window.location.href = '/login/';
        }, 2000);
    } catch (error) {
        console.error('Signup error:', error);
        toast.error(error.message || 'Registration failed');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
});
