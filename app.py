from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import base64
import time
import re

app = Flask(__name__)
CORS(app)

# =============================================================================
# CONFIGURAÇÕES GHOSTPAY - CREDENCIAIS DO VENDA HOJE
# =============================================================================

GHOSTPAY_URL = "https://api.ghostspaysv2.com/functions/v1/transactions"
SECRET_KEY = "sk_live_4rcXnqQ6KL4dJ2lW0gZxh9lCj5tm99kYMCk0i57KocSKGGD4"
COMPANY_ID = "43fc8053-d32c-4d37-bf93-33046dd7215b"

# Basic Auth encoding
auth_string = f"{SECRET_KEY}:"
basic_auth = base64.b64encode(auth_string.encode()).decode()

# =============================================================================
# CONFIGURAÇÕES ESPECÍFICAS DO VENDA HOJE
# =============================================================================

PRODUCT_NAME = "Mentoria Venda Hoje - Acesso Vitalício"
PRODUCT_PRICE = 890  # R$ 8,90 em centavos
COMPANY_EMAIL = "suporte.vendahoje@gmail.com"

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def clean_document(document):
    """Limpa CPF/CNPJ - remove caracteres não numéricos"""
    if document:
        return re.sub(r'\D', '', document)
    return "00000000191"  # CPF padrão

def get_customer_ip(request):
    """Obtém o IP real do cliente"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

# =============================================================================
# ROTAS PRINCIPAIS
# =============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK", "message": "API Venda Hoje"})

@app.route('/create-payment', methods=['POST', 'OPTIONS'])
def create_payment():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        
        print("=== DADOS RECEBIDOS DO FRONTEND VENDA HOJE ===")
        print(f"Dados: {data}")
        
        # Se o frontend não enviar dados específicos, usar padrão da mentoria
        if not data:
            return create_venda_hoje_payment()
        
        # Verificar se é a estrutura da landing page
        if 'customer' in data:
            customer = data['customer']
            amount = data.get('amount', PRODUCT_PRICE)
        else:
            # Usar dados padrão para compra única da mentoria
            return create_venda_hoje_payment()
        
        # Validar campos obrigatórios
        if not customer.get('name') or not customer.get('email'):
            return jsonify({
                "error": True,
                "message": "Nome e email do cliente são obrigatórios."
            }), 400
        
        # Validar valor mínimo
        if amount < 100:  # R$ 1,00 mínimo
            return jsonify({
                "error": True,
                "message": "Valor mínimo é R$ 1,00 (100 centavos)"
            }), 400
        
        # ✅ PAYLOAD CORRETO PARA VENDA HOJE
        payload = {
            "paymentMethod": "PIX",
            "customer": {
                "name": customer.get('name', 'Cliente Venda Hoje'),
                "email": customer.get('email', COMPANY_EMAIL),
                "phone": customer.get('phone', '11999999999'),
                "document": {
                    "number": clean_document(customer.get('document')),
                    "type": "CPF"
                }
            },
            "items": [
                {
                    "title": PRODUCT_NAME,
                    "unitPrice": amount,
                    "quantity": 1,
                    "externalRef": f"venda-hoje-{int(time.time())}"
                }
            ],
            "amount": amount,
            "description": data.get('description', PRODUCT_NAME),
            "postbackUrl": data.get('postbackUrl', ''),
            "metadata": {
                "product": "mentoria_venda_hoje",
                "access_type": "vitalicio",
                "source": "landing_page",
                "campaign": "venda_hoje_promo"
            },
            "pix": {},
            "expiresInDays": 1,
            "ip": get_customer_ip(request)
        }
        
        # ✅ HEADERS CORRETOS
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'authorization': f'Basic {basic_auth}',
            'Company-ID': COMPANY_ID
        }
        
        print("=== ENVIANDO PARA GHOSTPAY ===")
        print(f"URL: {GHOSTPAY_URL}")
        print(f"Payload: {payload}")
        
        # Fazer requisição para GhostPay
        response = requests.post(
            GHOSTPAY_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print("=== RESPOSTA GHOSTPAY ===")
        print(f"Status Code: {response.status_code}")
        
        # VERIFICAÇÃO CORRIGIDA: Aceitar 200 ou 201
        if response.status_code in [200, 201]:
            response_data = response.json()
            
            print(f"✅ Transação criada com sucesso! ID: {response_data.get('id')}")
            
            # Verificar se temos dados PIX
            if 'pix' in response_data and response_data['pix']:
                pix_data = response_data['pix']
                qr_code = pix_data.get('qrcode') or pix_data.get('qrCode')
                
                print(f"✅ QR Code recebido: {qr_code[:50]}..." if qr_code else "⚠️ QR Code não encontrado")
                
                # Retornar dados formatados para o frontend
                return jsonify({
                    "success": True,
                    "transaction": {
                        "id": response_data.get('id'),
                        "status": response_data.get('status'),
                        "amount": response_data.get('amount'),
                        "created_at": response_data.get('createdAt')
                    },
                    "pix": {
                        "qr_code": qr_code,
                        "code": qr_code,  # Usar o mesmo QR code como código
                        "expires_at": pix_data.get('expirationDate'),
                        "copy_paste": qr_code  # Usar o mesmo para copy_paste
                    }
                }), 200
            else:
                print("⚠️ Dados PIX não encontrados na resposta")
                return jsonify({
                    "error": True,
                    "message": "Dados PIX não recebidos da API",
                    "debug": "Nenhum campo 'pix' na resposta"
                }), 500
                
        else:
            error_details = response.text
            print(f"❌ ERRO GHOSTPAY: {error_details}")
            
            return jsonify({
                "error": True,
                "message": f"Erro na API GhostPay: {response.status_code}",
                "details": error_details,
                "status_code": response.status_code
            }), response.status_code
            
    except Exception as e:
        print(f"ERRO INTERNO: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            "error": True,
            "message": f"Erro interno: {str(e)}"
        }), 500

def create_venda_hoje_payment():
    """Cria pagamento padrão para a mentoria Venda Hoje"""
    try:
        # ✅ PAYLOAD PADRÃO PARA VENDA HOJE
        payload = {
            "paymentMethod": "PIX",
            "customer": {
                "name": "Cliente Venda Hoje",
                "email": COMPANY_EMAIL,
                "phone": "11999999999",
                "document": {
                    "number": "00000000191",
                    "type": "CPF"
                }
            },
            "items": [
                {
                    "title": PRODUCT_NAME,
                    "unitPrice": PRODUCT_PRICE,
                    "quantity": 1,
                    "externalRef": f"venda-hoje-{int(time.time())}"
                }
            ],
            "amount": PRODUCT_PRICE,
            "description": PRODUCT_NAME,
            "metadata": {
                "product": "mentoria_venda_hoje",
                "access_type": "vitalicio",
                "source": "landing_page",
                "campaign": "oferta_promocional"
            },
            "pix": {},
            "expiresInDays": 1
        }
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'authorization': f'Basic {basic_auth}',
            'Company-ID': COMPANY_ID
        }
        
        response = requests.post(
            GHOSTPAY_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code (padrão): {response.status_code}")
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            
            if 'pix' in response_data and response_data['pix']:
                pix_data = response_data['pix']
                qr_code = pix_data.get('qrcode') or pix_data.get('qrCode')
                
                return jsonify({
                    "success": True,
                    "transaction": {
                        "id": response_data.get('id'),
                        "status": response_data.get('status'),
                        "amount": response_data.get('amount')
                    },
                    "pix": {
                        "qr_code": qr_code,
                        "code": qr_code,
                        "copy_paste": qr_code
                    }
                }), 200
        
        return jsonify({
            "error": True,
            "message": f"Erro ao criar pagamento: {response.status_code}",
            "details": response.text[:200]
        }), response.status_code
        
    except Exception as e:
        return jsonify({
            "error": True,
            "message": f"Erro: {str(e)}"
        }), 500

@app.route('/check-payment/<transaction_id>', methods=['GET'])
def check_payment(transaction_id):
    """Verifica status de uma transação"""
    try:
        headers = {
            'accept': 'application/json',
            'authorization': f'Basic {basic_auth}',
            'Company-ID': COMPANY_ID
        }
        
        url = f"{GHOSTPAY_URL}/{transaction_id}"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "success": True,
                "status": data.get('status'),
                "paid_at": data.get('paidAt'),
                "transaction": data
            }), 200
        else:
            return jsonify({
                "error": True,
                "message": "Transação não encontrada",
                "details": response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            "error": True,
            "message": f"Erro: {str(e)}"
        }), 500

@app.route('/test-venda-hoje', methods=['GET'])
def test_venda_hoje():
    """Teste específico para a landing page Venda Hoje"""
    try:
        payload = {
            "customer": {
                "name": "Cliente Teste Venda Hoje",
                "email": "teste@vendahoje.com",
                "document": "12345678909"
            },
            "amount": 890,
            "description": "Teste de compra - Mentoria Venda Hoje"
        }
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json'
        }
        
        # Chamar a própria API
        import json
        from io import BytesIO
        
        # Simular requisição
        with app.test_client() as client:
            response = client.post(
                '/create-payment',
                data=json.dumps(payload),
                headers=headers,
                content_type='application/json'
            )
            
            return response.get_json(), response.status_code
            
    except Exception as e:
        return jsonify({
            "error": True,
            "message": f"Erro no teste: {str(e)}"
        }), 500

@app.route('/')
def home():
    return jsonify({
        "api": "Venda Hoje - Checkout API",
        "version": "1.0.0",
        "status": "online",
        "product": PRODUCT_NAME,
        "price": f"R$ {PRODUCT_PRICE / 100:.2f}",
        "endpoints": {
            "create_payment": "/create-payment (POST)",
            "check_payment": "/check-payment/<id> (GET)",
            "health": "/health (GET)",
            "test": "/test-venda-hoje (GET)"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("🚀 VENDA HOJE API - SISTEMA DE PAGAMENTO PIX")
    print("=" * 60)
    print(f"🔗 URL: http://localhost:{port}")
    print(f"📦 Produto: {PRODUCT_NAME}")
    print(f"💰 Preço: R$ {PRODUCT_PRICE / 100:.2f}")
    print(f"🔑 Credenciais configuradas: Sim")
    print("=" * 60)
    print("📝 Endpoints:")
    print(f"  • POST /create-payment   - Criar pagamento PIX")
    print(f"  • GET  /check-payment/id - Verificar status")
    print(f"  • GET  /test-venda-hoje  - Teste da API")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)