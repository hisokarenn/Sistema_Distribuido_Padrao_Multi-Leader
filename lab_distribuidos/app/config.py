SERVERS = {
    'A': {
        'host': 'localhost', # Este é o 'localhost'
        'port': 5432,
        'dbname': 'db_a',
        'user': 'user_a',
        'password': 'pass_a',
        'tipo': 'lider'
    },
    'B': {
        'host': 'IP', # (TROCAR PELO IP REAL DA MÁQUINA B)
        'port': 5433,
        'dbname': 'db_b',
        'user': 'user_b',
        'password': 'pass_b',
        'tipo': 'lider'
    },
    'C': { 
        'host': 'IP', # (TROCAR PELO IP REAL DA MÁQUINA C)
        'port': 5434,
        'dbname': 'db_c',
        'user': 'user_c',
        'password': 'pass_c',
        'tipo': 'lider'
    },
    'D': {
        'host': 'IP', # (TROCAR PELO IP REAL DA MÁQUINA D)
        'port': 5435,
        'dbname': 'db_d',
        'user': 'user_d',
        'password': 'pass_d',
        'tipo': 'lider'
    }
}

ALL_SERVERS = ['A', 'B', 'C', 'D'] 
LEADER_SERVERS = ['A', 'B', 'C', 'D'] 

LOCAL_SERVERS = ['A'] # (Continua 'A')