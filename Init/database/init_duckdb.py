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
        queries = [
            """ CREATE TABLE IF NOT EXISTS raw.clients (
                client_id INT PRIMARY KEY,
                nom_client TEXT,
                email TEXT, 
                ville TEXT,
                pays TEXT, 
                genre TEXT
            )""",
            """ CREATE TABLE IF NOT EXISTS raw.commandes (
                commande_id INT PRIMARY KEY,
                client_id INT, 
                date_commande DATE, 
                montant_total DECIMAL(10,2), 
                statut TEXT
            )""",
            """ CREATE TABLE IF NOT EXISTS raw.details_commandes (
                commande_id INT, 
                produit_id INT, 
                quantite INT, 
                prix_unitaire DECIMAL(10,2), 
                sous_total DECIMAL(10,2)
            )""",
            """ CREATE TABLE IF NOT EXISTS raw.produits (
                produit_id INT PRIMARY KEY, 
                nom_produit TEXT, 
                prix_unitaire DECIMAL(10,2), 
                stock INT
            )""",
            """ CREATE TABLE IF NOT EXISTS raw.paiements (
                paiement_id INT PRIMARY KEY, 
                commande_id INT, 
                mode_paiement TEXT, 
                statut_paiement TEXT, 
                date_paiement DATE
            )"""
        ]
        for query in queries:
            self.conn.execute(query)
        logging.info("Raw tables created.")

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
