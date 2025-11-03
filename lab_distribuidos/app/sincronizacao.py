import psycopg2
from psycopg2.extras import execute_values
from app.config import SERVERS, LOCAL_SERVERS, ALL_SERVERS

def connect_to_db(servidor_id):
    """Conecta ao banco de dados específico."""
    config = SERVERS.get(servidor_id)
    if not config:
        return None
    
    connect_args = {k: v for k, v in config.items() if k != 'tipo'}
    connect_args['connect_timeout'] = 5
    
    try:
        conn = psycopg2.connect(**connect_args)
        return conn
    except psycopg2.OperationalError:
        return None

def fetch_all_data_from_server(conn, tabela):
    """Busca todos os dados (id e timestamp) de uma tabela."""
    cursor = conn.cursor()
    try:
        if tabela == 'disciplinas':
            # Usa data_ultima_modificacao para LWW
            cursor.execute(f"SELECT id, data_ultima_modificacao FROM {tabela}")
        elif tabela == 'matriculas':
            # Usa data_ultima_modificacao para LWW
            cursor.execute(f"SELECT id, data_ultima_modificacao FROM {tabela}")
        elif tabela == 'deleted_disciplinas' or tabela == 'deleted_matriculas':
            cursor.execute(f"SELECT id, timestamp FROM {tabela}")
        
        return {row[0]: row[1:] for row in cursor.fetchall()}
    
    except psycopg2.Error as e:
        print(f"Erro ao buscar dados da tabela {tabela}: {e}")
        return {}
    finally:
        cursor.close()

def merge_data(conn_local, conn_remoto, tabela, deleted_ids_local=set()):
    """
    Executa o "merge" (LWW) dos dados do remoto para o local.
    """
    print(f"🔄 Sincronizando tabela '{tabela}'...")
    
    dados_locais = fetch_all_data_from_server(conn_local, tabela)
    dados_remotos = fetch_all_data_from_server(conn_remoto, tabela)
    
    cursor_local = conn_local.cursor()
    cursor_remoto = conn_remoto.cursor()
    
    ids_para_sincronizar = []

    # 1. Encontrar dados que o Remoto tem e o Local não, ou que são mais novos no Remoto
    for uuid, dados_remotos_ts_tuple in dados_remotos.items():
        
        # LÓGICA ANTI-RESSURREIÇÃO (Ignora se o item foi deletado localmente)
        if uuid in deleted_ids_local:
            continue 

        dados_locais_ts_tuple = dados_locais.get(uuid)
        
        # Pega o timestamp (é o primeiro item da tupla)
        dados_remotos_ts = dados_remotos_ts_tuple[0]
        dados_locais_ts = dados_locais_ts_tuple[0] if dados_locais_ts_tuple else None

        # Lógica LWW (Last Write Wins)
        if (uuid not in dados_locais) or (dados_remotos_ts > dados_locais_ts):
            ids_para_sincronizar.append(uuid)

    if not ids_para_sincronizar:
        print(f"✅ Tabela '{tabela}' já está sincronizada.")
        cursor_local.close()
        cursor_remoto.close()
        return

    print(f"Merging {len(ids_para_sincronizar)} registros da tabela '{tabela}'...")

    # 2. Buscar os dados completos dos IDs selecionados do Remoto
    try:
        # Define as colunas e regras de update para cada tabela
        if tabela == 'disciplinas':
            cursor_remoto.execute(f"SELECT * FROM disciplinas WHERE id = ANY(%s::uuid[])", (ids_para_sincronizar,))
            colunas_query = "(id, nome, vagas_totais, is_deleted, data_ultima_modificacao)" # 5 COLUNAS
            update_set = """
                nome = EXCLUDED.nome, 
                vagas_totais = EXCLUDED.vagas_totais, 
                is_deleted = EXCLUDED.is_deleted, 
                data_ultima_modificacao = EXCLUDED.data_ultima_modificacao
            """
            update_where = "disciplinas.data_ultima_modificacao < EXCLUDED.data_ultima_modificacao"
            
        elif tabela == 'matriculas':
            cursor_remoto.execute(f"SELECT * FROM matriculas WHERE id = ANY(%s::uuid[])", (ids_para_sincronizar,))
            colunas_query = "(id, disciplina_id, nome_aluno, timestamp_matricula, status, data_ultima_modificacao)" # 6 COLUNAS
            update_set = """
                disciplina_id = EXCLUDED.disciplina_id, 
                nome_aluno = EXCLUDED.nome_aluno, 
                timestamp_matricula = EXCLUDED.timestamp_matricula, 
                status = EXCLUDED.status, 
                data_ultima_modificacao = EXCLUDED.data_ultima_modificacao
            """
            update_where = "matriculas.data_ultima_modificacao < EXCLUDED.data_ultima_modificacao"
        
        elif tabela == 'deleted_disciplinas' or tabela == 'deleted_matriculas':
            cursor_remoto.execute(f"SELECT * FROM {tabela} WHERE id = ANY(%s::uuid[])", (ids_para_sincronizar,))
            colunas_query = "(id, timestamp)"
            update_set = "timestamp = EXCLUDED.timestamp"
            update_where = f"{tabela}.timestamp < EXCLUDED.timestamp"

        registros_completos = cursor_remoto.fetchall()

        # 3. Aplicar no banco Local usando "INSERT ... ON CONFLICT"
        if registros_completos:
            
            # Query unificada que usa o 'placeholder %s' para execute_values
            query = f"""
                INSERT INTO {tabela} {colunas_query}
                VALUES %s 
                ON CONFLICT (id) DO UPDATE SET {update_set}
                WHERE {update_where};
            """
            
            execute_values(cursor_local, query, registros_completos)
            conn_local.commit()
            print(f"✅ Merge da tabela '{tabela}' concluído.")

    except Exception as e:
        conn_local.rollback()
        print(f"❌ ERRO durante o merge da tabela '{tabela}': {e}")
    finally:
        cursor_local.close()
        cursor_remoto.close()

def fetch_deleted_ids(conn, tabela_tombstone):
    """Busca todos os IDs da tabela de deleção."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT id FROM {tabela_tombstone}")
        return {row[0] for row in cursor.fetchall()}
    except psycopg2.Error:
        return set()
    finally:
        cursor.close()

def sincronizar_ao_iniciar():
    """Função principal de "cura" (healing) para ser chamada pelo main.py."""
    
    print("\n" + "="*50)
    print("INICIANDO PROCESSO DE SINCRONIZAÇÃO (HEALING)")
    print("="*50)

    lider_local_id = LOCAL_SERVERS[0]
    lideres_remotos_ids = [s for s in ALL_SERVERS if s != lider_local_id]

    conn_local = connect_to_db(lider_local_id)
    if not conn_local:
        print(f"❌ Falha crítica: Não foi possível conectar ao banco de dados local ({lider_local_id}). Sincronização abortada.")
        return

    # Busca os IDs deletados localmente ANTES de sincronizar
    deleted_disciplinas_local = fetch_deleted_ids(conn_local, 'deleted_disciplinas')
    deleted_matriculas_local = fetch_deleted_ids(conn_local, 'deleted_matriculas')

    for remoto_id in lideres_remotos_ids:
        print(f"\n--- Tentando sincronizar com o Líder {remoto_id} ---")
        conn_remoto = connect_to_db(remoto_id)
        
        if not conn_remoto:
            print(f"⚠️ Líder {remoto_id} está OFFLINE. Pulando sincronização.")
            continue

        deleted_disciplinas_remoto = fetch_deleted_ids(conn_remoto, 'deleted_disciplinas')
        deleted_matriculas_remoto = fetch_deleted_ids(conn_remoto, 'deleted_matriculas')
            
        try:
            # Sincronização Bi-Direcional:
            
            # 1. Puxar dados do Remoto (ex: B) para o Local (ex: A)
            print(f"\n[{lider_local_id} <- {remoto_id}] Puxando dados do {remoto_id} para {lider_local_id}...")
            # Sincroniza deleções primeiro
            merge_data(conn_local, conn_remoto, 'deleted_disciplinas') 
            merge_data(conn_local, conn_remoto, 'deleted_matriculas')
            
            merge_data(conn_local, conn_remoto, 'disciplinas', deleted_ids_local=deleted_disciplinas_local)
            merge_data(conn_local, conn_remoto, 'matriculas', deleted_ids_local=deleted_matriculas_local)
            
            # 2. Empurrar dados do Local (ex: A) para o Remoto (ex: B)
            print(f"\n[{lider_local_id} -> {remoto_id}] Empurrando dados do {lider_local_id} para {remoto_id}...")
            # Sincroniza deleções primeiro
            merge_data(conn_remoto, conn_local, 'deleted_disciplinas') 
            merge_data(conn_remoto, conn_local, 'deleted_matriculas')

            merge_data(conn_remoto, conn_local, 'disciplinas', deleted_ids_local=deleted_disciplinas_remoto)
            merge_data(conn_remoto, conn_local, 'matriculas', deleted_ids_local=deleted_matriculas_remoto)
            
            print(f"\n✅ Sincronização com {remoto_id} concluída.")

        except Exception as e:
            print(f"❌ Erro inesperado durante a sincronização com {remoto_id}: {e}")
        finally:
            if conn_remoto:
                conn_remoto.close()

    if conn_local:
        conn_local.close()
        
    print("="*50)
    print("SINCRONIZAÇÃO CONCLUÍDA")
    print("="*50)