$(document).ready(function(){
  $('#cadastroForm').submit(function(e){
    e.preventDefault();

    const nome = $('#nome').val().trim();
    const email = $('#email').val().trim();
    const senha = $('#senha').val().trim();
    const confirmSenha = $('#confirmPassword').val().trim();

    if (!nome || !email || !senha || !confirmSenha) {
      alert('Preencha todos os campos.');
      return;
    }

    if (senha !== confirmSenha) {
      alert('As senhas não conferem.');
      return;
    }

    $.ajax({
      url: 'http://localhost:3000/register',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ nome, email, senha }),
      success: function() {
        alert('Cadastro realizado com sucesso! Faça login.');
        window.location.href = 'entreoucadastrese.html';
      },
      error: function() {
        alert('Erro ao tentar cadastrar. Tente novamente mais tarde!');
      }
    });
  });
});
