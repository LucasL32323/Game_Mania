$(document).ready(function() {
    $('#loginForm').on('submit', function(e) {
        e.preventDefault();

        const email = $('#loginemail').val();
        const password = $('#loginPassword').val();

        $.ajax({
            url: 'http://localhost:3000/login',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email: email, password: password }),
            success: function(data) {
                if (data.success) {
                    localStorage.setItem('usuario_logado', JSON.stringify(data.user));
                    alert('Login realizado com sucesso');
                    window.location.href = 'index.html';
                } else {
                    alert(data.message);
                }
            },
            error: function(xhr, status, error) {
                console.error(error);
                alert('Erro ao tentar fazer login: ' + (xhr.responseJSON?.message || 'Erro no servidor'));
            }
        });
    });
});
