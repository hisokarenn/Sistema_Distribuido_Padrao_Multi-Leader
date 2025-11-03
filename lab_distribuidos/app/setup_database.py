import psycopg2
from psycopg2 import OperationalError
from app.config import SERVERS 


def verificar_conexao_servidor(servidor_id, config):
    """
    Tenta conectar ao banco de dados PostgreSQL e reporta o status.
    """
    host = config['host']
    port = config['port']

    print(f"\n--- Verificando Servidor {servidor_id} ({host}:{port}) ---")
    conn = None

    try:
        # Tenta estabelecer a conexão com um timeout de 5 segundos
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=config['dbname'],
            user=config['user'],
            password=config['password'],
            connect_timeout=5
        )
        print(f"✅ SUCESSO! Conexão com o Servidor {servidor_id} estabelecida.")

        # Teste rápido de consulta para garantir que o banco está operacional
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        print(f"   Status do DB: Responde a consultas SQL básicas.")
        cursor.close()

    except OperationalError as e:
        print(f"❌ FALHA! Não foi possível conectar ao Servidor {servidor_id}.")
        print(f"   Detalhes do erro: {e}")
        print("\n   *Possíveis Soluções:*")
        print("   - Verifique se a máquina (host) está ligada.")
        print("   - Verifique as configurações de rede (Firewall/pg_hba.conf) ou credenciais.")

    except Exception as e:
        print(
            f"❓ ERRO INESPERADO ao testar o Servidor {servidor_id}: {type(e).__name__}: {e}")

    finally:
        if conn:
            conn.close()
            print(f"   Conexão com {servidor_id} fechada.")


def verificar_conexao_menu():
    """Função principal para ser chamada pelo menu do main.py."""

    if not SERVERS:
        print("❌ ERRO: O dicionário SERVERS está vazio no seu arquivo app/config.py.")
        return

    print("\n*** INICIANDO VERIFICAÇÃO DE CONEXÃO DOS SERVIDORES ***")

    # Itera sobre todos os servidores definidos no seu config.py
    for servidor_id, config in SERVERS.items():
        verificar_conexao_servidor(servidor_id, config)

    print("\n*** VERIFICAÇÃO CONCLUÍDA ***")
