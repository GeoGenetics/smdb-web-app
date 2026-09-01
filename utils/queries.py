import os, sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

import pandas as pd
import psycopg2
from psycopg2 import sql


def upload_id_filter(schema, table, upload_id):
    q = f'''
    select * from "{schema}"."{table}" where upload_uuid = '{upload_id}'
    '''
    return q

def check_if_upload_id_exists_in_table(schema, table, upload_id, engine):
    '''
    Returns true if upload_id exists in the upload_uuid column of schema.table
    '''
    if "upload_uuid" in get_column_names(table_name=table, schema_name=schema, engine=engine):
    
        q = upload_id_filter(schema, table, upload_id)
        df = pd.read_sql(sql=q, con=engine)
        if len(df) != 0:
            return True
        else:
            return False
    else:
        return False

def get_unique_values_from_db_column(schema: str, table: str, column: str, engine, lower: bool=True) -> set:
    if lower:
        return set(get_table_as_dataframe(engine, schema_name=schema, table_name=table)[column].astype(str).str.lower().unique())
    else:
        return set(get_table_as_dataframe(engine, schema_name=schema, table_name=table)[column].astype(str).unique())
    
def check_if_upload_id_exists_in_schema(database, schema, upload_id, engine):
    cases = []
    table_names = get_table_names(schema, database, engine)
    for table in table_names:
        if check_if_upload_id_exists_in_table(schema, table, upload_id, engine):
            cases.append(table)
    return cases
    

def get_foreign_table_names(local_schema, engine, foreign_server):
    q = f'''
    SELECT
    n.nspname AS local_schema,
    c.relname AS local_table,
    s.srvname AS foreign_server,
    ftoptions
FROM pg_foreign_table ft
JOIN pg_class c ON c.oid = ft.ftrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_foreign_server s ON s.oid = ft.ftserver
WHERE s.srvname = '{foreign_server}' and n.nspname='{local_schema}';
    '''
    df = pd.read_sql(sql=q, con=engine)
    return list(df['local_table'])

def get_table_names(schema_name, database_name, engine):
    q = f'''    
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = '{schema_name}' and table_catalog = '{database_name}' and table_type = 'BASE TABLE';
    '''
    df = pd.read_sql(sql=q, con=engine)
    return list(df['table_name'])

def get_primary_key(table_name, schema_name, database_name, engine):
    q = f'''
    SELECT 
    column_name
    FROM 
        information_schema.table_constraints AS tc
    JOIN 
        information_schema.key_column_usage AS kcu 
        ON tc.constraint_name = kcu.constraint_name
    WHERE 
        tc.constraint_type = 'PRIMARY KEY' 
        and tc.table_name = '{table_name}'
        and tc.table_schema = '{schema_name}'
        and kcu.constraint_schema = '{schema_name}'
        and tc.table_catalog = '{database_name}'
    '''
    df = pd.read_sql_query(q, engine)
    return list(df['column_name'])

def get_geo_distances_from_db_table(latitiude_coord,
                                longitude_coord,
                                table,
                                schema, 
                                longitude_column_name, 
                                latitude_column_name,  
                                db_engine,
                                distance_threshold: int=None):
    
    '''
    Returns a dataframe with a distance column added that contains the distance from the input coordinates to the
    coordinates in the table.
    
    If distance_threshold is set, only records where distance (m) is lower than distance_threshold (m) will be returned. 
    '''
    
    query = f'''
    SELECT *, (point({longitude_column_name}, {latitude_column_name}) <@> point({longitude_coord}, {latitiude_coord})) * 1609.344 AS distance
    FROM
    "{schema}"."{table}"
    '''
         
    if distance_threshold:
        query = f'''
        SELECT *, (point({longitude_column_name}, {latitude_column_name}) <@> point({longitude_coord}, {latitiude_coord})) * 1609.344 AS distance
        FROM
        "{schema}"."{table}"
        WHERE
            (point({longitude_column_name}, {latitude_column_name}) <@> point({longitude_coord}, {latitiude_coord})) < ({distance_threshold} / 1609.344)
        ORDER BY
        distance;
        '''   
    
    return pd.read_sql(query, db_engine)
    

def get_table_information(table_name, schema_name, engine):
    f'''
    Returns a dataframe with the following details about a table:
    
    ['table_catalog', 'table_schema', 'table_name', 'column_name',
       'ordinal_position', 'column_default', 'is_nullable', 'data_type',
       'character_maximum_length', 'character_octet_length',
       'numeric_precision', 'numeric_precision_radix', 'numeric_scale',
       'datetime_precision', 'interval_type', 'interval_precision',
       'character_set_catalog', 'character_set_schema', 'character_set_name',
       'collation_catalog', 'collation_schema', 'collation_name',
       'domain_catalog', 'domain_schema', 'domain_name', 'udt_catalog',
       'udt_schema', 'udt_name', 'scope_catalog', 'scope_schema', 'scope_name',
       'maximum_cardinality', 'dtd_identifier', 'is_self_referencing',
       'is_identity', 'identity_generation', 'identity_start',
       'identity_increment', 'identity_maximum', 'identity_minimum',
       'identity_cycle', 'is_generated', 'generation_expression',
       'is_updatable']
    '''

    column_query = f'''
    SELECT *
    FROM information_schema.columns 
    WHERE table_schema = '{schema_name}' AND table_name = '{table_name}' 
    ORDER BY ordinal_position;
    '''
    df = pd.read_sql_query(column_query, engine)
       
    return df


def get_table_dtypes(table_name, schema_name, engine):
    '''
    Note: this returns all columns, also autogenerated ones.
    '''
    return get_table_information(table_name, schema_name, engine)[['table_name', 'column_name', 'data_type', 'udt_name']]

def get_db_schema(name_maps_schema_name, engine):
    q = f'''
    select * from "{name_maps_schema_name}".all_names;
    '''
    return pd.read_sql(q, engine)

def get_possible_datatypes(category, engine):
    match(category):
        case "date":
            code = "D"
        case "boolean":
            code = "B"
        case "string":
            code = "S"
        case _:
            raise Exception("Unknown category")

    q = f'''
    SELECT typname
    FROM pg_catalog.pg_type
    WHERE typcategory = '{code}';
    '''

    df = pd.read_sql_query(q, engine)
    return list(df['typname'])

    # Connect to PostgreSQL database
def count_rows(sql_alch_db_config, table_name):
    database = sql_alch_db_config['database']
    schema = sql_alch_db_config['schema_name']
    
    conn = psycopg2.connect(
        host=sql_alch_db_config['host'],
        port=sql_alch_db_config['port'],
        database=database,
        user=sql_alch_db_config['user'],
        password=sql_alch_db_config['password'],
    )
    
    # Create a cursor object
    cursor = conn.cursor()
    
    try:
        # Execute SQL query to count rows of the table
        query = sql.SQL('SELECT COUNT(*) FROM {}.{}').format(
            sql.Identifier(schema),
            sql.Identifier(table_name),
        )
        cursor.execute(query)
        
        # Fetch the result
        row_count = cursor.fetchone()[0]
        
        return row_count
    except (Exception, psycopg2.Error) as error:
        print("Error counting rows:", error)
    finally:
        # Close the cursor and connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
def get_column_names(table_name, schema_name, engine):
    df = get_table_information(table_name=table_name, schema_name=schema_name, engine=engine)
    return list(df["column_name"])


def get_schema_names(engine):
    q = '''
    SELECT schema_name
    FROM information_schema.schemata;
    '''
    
    df = pd.read_sql(q, con=engine)
    return df

def get_table_as_dataframe(engine, schema_name: str, table_name: str, dtype=None):
    q = f'''
    SELECT *
    FROM "{schema_name}"."{table_name}";
    '''
    
    df = pd.read_sql(q, con=engine, dtype=dtype)
    return df



    # except (Exception, psycopg2.Error) as error:
    #     raise

def get_table_as_df(schema_name: str, table_name: str, sql_alch_config):
    
    q = f'''
    select * from "{schema_name}"."{table_name}";
    '''
    
    df = pd.read_sql(q, sql_alch_config)
    
    return df


def execute_query(query, connection, params=None, get_cols=False):
    # Connection parameters

    # try:
        # Establish a connection
        with connection as conn:
            # Create a cursor
            with conn.cursor() as cur:
                # Execute the query
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)

                # Fetch results if it's a SELECT query
                if query.strip().upper().startswith("SELECT"):

                    if get_cols:
                        return cur.fetchall(), cur.description

                    else:
                        return cur.fetchall()

                else:
                    # For INSERT, UPDATE, DELETE queries
                    conn.commit()
                    return cur.rowcount
