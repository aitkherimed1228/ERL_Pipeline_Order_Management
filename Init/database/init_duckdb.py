import duckdb
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[  # Added a missing comma here
        logging.FileHandler("etl_pipeline.log"),
        logging.StreamHandler()
    ]
)


class ETLPipeline:  
    def __init__(self, db_path="ecommerce.db"):
        self.conn = duckdb.connect(db_path)
        logging.info("Connected to DuckDB.")

    def setup_schemas(self):
        """Create schemas: raw, refined, and report."""
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        logging.info("Schema created: raw.")

        self.conn.execute("CREATE SCHEMA IF NOT EXISTS refined")
        logging.info("Schema created: refined.")

        self.conn.execute("CREATE SCHEMA IF NOT EXISTS report")
        logging.info("Schema created: report.")

    def create_tables(self):
        """Create raw tables in DuckDB."""
        raw_querie =""" CREATE TABLE IF NOT EXISTS raw.ecom_db (
                client_id INT,
                nom_client TEXT,
                email TEXT, 
                ville TEXT,
                pays TEXT, 
                genre TEXT,       
                commande_id INT,
                date_commande DATE, 
                montant_total DECIMAL(10,2), 
                statut TEXT,
                produit_id INT, 
                nom_produit TEXT, 
                prix_unitaire DECIMAL(10,2), 
                quantite INT, 
                sous_total DECIMAL(10,2), 
                stock INT,
                paiement_id INT , 
                mode_paiement TEXT, 
                statut_paiement TEXT, 
                date_paiement DATE,
                Datetime_ingestion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        
        self.conn.execute(raw_querie)
        logging.info("Raw table 'ecom_db' created successfully.")

        refined_queries = [
            """CREATE TABLE IF NOT EXISTS refined.clients (
                client_id INT PRIMARY KEY,
                nom_client TEXT,
                email TEXT, 
                ville TEXT,
                pays TEXT, 
                genre TEXT
            )"""
            ,
            """ CREATE TABLE IF NOT EXISTS refined.commandes (
                commande_id INT PRIMARY KEY,
                client_id INT, 
                date_commande DATE, 
                montant_total DECIMAL(10,2), 
                statut TEXT
            )"""
            ,
            """ CREATE TABLE IF NOT EXISTS refined.details_commandes (
                commande_id INT, 
                produit_id INT, 
                quantite INT, 
                prix_unitaire DECIMAL(10,2), 
                sous_total DECIMAL(10,2)
            )"""
            ,
            """ CREATE TABLE IF NOT EXISTS refined.produits (
                produit_id INT PRIMARY KEY, 
                nom_produit TEXT, 
                prix_unitaire DECIMAL(10,2), 
                stock INT
            )"""
            ,
            """ CREATE TABLE IF NOT EXISTS refined.paiements (
                paiement_id INT PRIMARY KEY, 
                commande_id INT, 
                mode_paiement TEXT, 
                statut_paiement TEXT, 
                date_paiement DATE
                
            )"""
        ]
        for query in refined_queries:
            self.conn.execute(query)
        logging.info("Refined tables 'clients , commandes , details_commandes , produits , paiements' created successfully.")

        
    def close_connection(self):
        """Close the DuckDB connection."""
        self.conn.close()
        logging.info("Closed DuckDB connection.")


if __name__ == "__main__":
    etl_pipeline = ETLPipeline()
    etl_pipeline.setup_schemas()
    etl_pipeline.create_tables()
    etl_pipeline.close_connection()
    logging.info("ETL process completed successfully.")
