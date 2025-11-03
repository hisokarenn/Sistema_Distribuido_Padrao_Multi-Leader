import psycopg2
from prettytable import PrettyTable
from collections import defaultdict
from app.config import SERVERS, ALL_SERVERS 

def connect_to_any_db(servidores_ids):
    for servidor_id in servidores_ids:
        config = SERVERS.get(servidor_id)
        if not config: continue
        connect_args = {k: v for k, v in config.items() if k != 'tipo'}
        connect_args['connect_timeout'] = 3
        try:
            conn = psycopg2.connect(**connect_args)
            print(f"✅ Conectado com sucesso ao Líder {servidor_id} para leitura de consolidação.")
            return conn, servidor_id
        except psycopg2.OperationalError:
            continue
    return None, None

def gerar_relatorio(): 
    conn, servidor_id = connect_to_any_db(ALL_SERVERS)
    if not conn:
        print("\n❌ Não foi possível conectar a nenhum líder para gerar o relatório consolidado.")
        return
    cursor = conn.cursor()
    print(f"\n--- Relatório Consolidado (Fonte de Dados: Líder {servidor_id}) ---")
    try:
        
        cursor.execute("""
            SELECT id, nome, vagas_totais  FROM disciplinas 
            WHERE (is_deleted IS NULL OR is_deleted = false) ORDER BY id;
        """)
        disciplinas_info = {row[0]: {'nome': row[1], 'vagas_totais': row[2]} for row in cursor.fetchall()}
        if not disciplinas_info:
            print("Nenhuma disciplina encontrada no catálogo.")
            return
        
        
        cursor.execute("SELECT disciplina_id, status FROM matriculas WHERE status = 'ACEITA';")
        matriculas_aceitas = cursor.fetchall()

        vagas_ocupadas = defaultdict(int)
        for disc_id, status in matriculas_aceitas:
            vagas_ocupadas[disc_id] += 1

        table = PrettyTable()
        table.field_names = ["ID", "Disciplina", "Vagas Totais", "Vagas Ocupadas", "Vagas Disponíveis"]
        table.align = "l"
        for disc_id, info in disciplinas_info.items():
            if disc_id not in vagas_ocupadas:
                vagas_ocupadas[disc_id] = 0
            nome = info['nome']
            vagas_totais = info['vagas_totais']
            ocupadas = vagas_ocupadas[disc_id]
            disponiveis = vagas_totais - ocupadas
            table.add_row([disc_id, nome, vagas_totais, ocupadas, disponiveis])
        print(table)
        print("----------------------------------------------------------------\n")
    except psycopg2.Error as e:
        print(f"❌ Erro SQL: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()