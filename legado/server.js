const bcrypt = require('bcrypt');
const saltRounds = 10;
const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const bodyParser = require('body-parser');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const db = mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: 'root',
    database: 'game_mania'
});

db.connect((err) => {
    if (err) {
        console.error('Erro ao conectar no BD: ', err);
        return;
    } else {
        console.log('Conectado ao banco de dados MySQL.');
    }
});

app.post('/register', async (req, res) => {
    const { nome, email, senha } = req.body;
    try {
        const hash = await bcrypt.hash(senha, saltRounds);
        const sql = 'INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)';
        db.query(sql, [nome, email, hash], (err, result) => {
            if (err) {
                return res.status(500).json({ message: 'Erro ao cadastrar usuário.' });
            }
            res.json({ message: 'Usuário cadastrado com sucesso!' });
        });
    } catch (error) {
        res.status(500).json({ message: 'Erro no servidor ao criptografar a senha.' });
    }
});

app.post('/login', (req, res) => {
    const { email, password } = req.body;
    const sql = 'SELECT * FROM usuarios WHERE email = ?';
    db.query(sql, [email], async (err, results) => {
        if (err) return res.status(500).json({ error: err });
        if (results.length > 0) {
            const user = results[0];
            const match = await bcrypt.compare(password, user.senha_hash);
            if (match) {
                res.json({
                    success: true,
                    user: {
                        id: user.id,
                        nome: user.nome,
                        email: user.email,
                        is_admin: user.is_admin
                    }
                });
            } else {
                res.json({ success: false, message: 'E-mail ou senha incorretos.' });
            }
        } else {
            res.json({ success: false, message: 'E-mail ou senha incorretos.' });
        }
    });
});

app.post('/checkout', (req, res) => {
    const { usuario_Id, cart, total } = req.body;
    if (!usuario_Id) return res.status(401).json({ message: 'Usuário não está logado' });

    const sqlPedido = 'INSERT INTO pedidos (usuario_id, valor_total) VALUES (?, ?)';
    db.query(sqlPedido, [usuario_Id, total], (err, result) => {
        if (err) return res.status(500).json({ message: 'Erro ao processar o pedido' });

        const pedidoID = result.insertId;
        const ItensValues = cart.map(item => [pedidoID, item.title, item.price, item.qty]);
        const sqlItens = 'INSERT INTO itens_pedido (pedido_id, produto_nome, preco_unitario, quantidade) VALUES ?';

        db.query(sqlItens, [ItensValues], (errItens) => {
            if (errItens) return res.status(500).json({ message: 'Erro ao adicionar itens ao pedido' });
            res.json({ message: 'Pedido realizado com sucesso', success: true, pedidoId: pedidoID });
        });
    });
});

app.get('/meus-pedidos/:userId', (req, res) => {
    const userId = req.params.userId;
    const sql = 'SELECT id, valor_total, status, data_pedido FROM pedidos WHERE usuario_id = ? ORDER BY id DESC';
    db.query(sql, [userId], (err, results) => {
        if (err) return res.status(500).json({ message: 'Erro ao buscar pedidos' });
        res.json(results);
    });
});

app.listen(3000, () => {
    console.log('Servidor rodando na porta 3000. Acesse em http://localhost:3000');
});
