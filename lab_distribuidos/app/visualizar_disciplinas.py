import psycopg2
from app.config import SERVERS, ALL_SERVERS 
from prettytable import PrettyTable

def connect_to_any_db(servidores_ids):
    for servidor_id in servidores_ids:
        config = SERVERS.get(servidor_id)
        if not config: continue
        connect_args = {k: v for k, v in config.items() if k != 'tipo'}
        connect_args['connect_timeout'] = 3 
        try:
            conn = psycopg2.connect(**connect_args)
            return conn, servidor_id
        except psycopg2.OperationalError:
            continue
    return None, None

def visualizar_disciplinas():
    conn, servidor_id = connect_to_any_db(ALL_SERVERS)
    if not conn:
        print("\n❌ Não foi possível conectar a nenhum servidor para visualizar disciplinas.")
        return
    cursor = conn.cursor()
    try:
        
        cursor.execute("""
            SELECT id, nome, vagas_totais 
            FROM disciplinas 
            WHERE (is_deleted IS NULL OR is_deleted = false) 
            ORDER BY nome;
        """)
        rows = cursor.fetchall()
        if not rows:
            print("Nenhuma disciplina encontrada no catálogo.")
            return
        table = PrettyTable()
        table.field_names = ["ID", "Disciplina", "Vagas Totais"]
        for row in rows:
            table.add_row(row)
        table.align = "l"
        print(f"\n=== Catálogo de Disciplinas (Fonte: Servidor {servidor_id}) ===")
        print(table)
        print("====================================================\n")
    except psycopg2.Error as e:
        print(f"❌ Erro SQL ao buscar disciplinas: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()