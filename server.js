const express = require('express');
const cors = require('cors');
const axios = require('axios');
const app = express();

app.use(cors());
app.use(express.json());

const GHOSTSPAYS_CONFIG = {
    secretKey: 'sk_live_4rcXnqQ6KL4dJ2lW0gZxh9lCj5tm99kYMCk0i57KocSKGGD4',
    companyId: '43fc8053-d32c-4d37-bf93-33046dd7215b',
    apiUrl: 'https://api.ghostspaysv2.com/functions/v1'
};

// Rota para criar transação PIX
app.post('/api/create-pix', async (req, res) => {
    try {
        const response = await axios.post(
            `${GHOSTSPAYS_CONFIG.apiUrl}/transactions`,
            {
                amount: req.body.amount || 8.90,
                currency: "BRL",
                paymentMethod: "PIX",
                description: req.body.description || "Mentoria Venda Hoje",
                metadata: req.body.metadata || {}
            },
            {
                headers: {
                    'Authorization': `Bearer ${GHOSTSPAYS_CONFIG.secretKey}`,
                    'Company-ID': GHOSTSPAYS_CONFIG.companyId,
                    'Content-Type': 'application/json'
                }
            }
        );
        res.json(response.data);
    } catch (error) {
        console.error('Erro GhostsPays:', error.response?.data || error.message);
        res.status(500).json({ error: 'Erro ao criar transação' });
    }
});

// Rota para verificar transação
app.get('/api/check-transaction/:id', async (req, res) => {
    try {
        const response = await axios.get(
            `${GHOSTSPAYS_CONFIG.apiUrl}/transactions/${req.params.id}`,
            {
                headers: {
                    'Authorization': `Bearer ${GHOSTSPAYS_CONFIG.secretKey}`,
                    'Company-ID': GHOSTSPAYS_CONFIG.companyId
                }
            }
        );
        res.json(response.data);
    } catch (error) {
        console.error('Erro GhostsPays:', error.response?.data || error.message);
        res.status(500).json({ error: 'Erro ao verificar transação' });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Servidor rodando na porta ${PORT}`);
});