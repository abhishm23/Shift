import duckdb

con = duckdb.connect(':memory:')
print("Scanning dataset_stress_4gb_plus_wide.csv via DuckDB...")
query = """
SELECT 
    COUNT(*) as total_rows,
    ROUND(SUM(extended_list_amt), 2) as total_gross,
    ROUND(SUM(net_invoiced_amt), 2) as total_net
FROM read_csv_auto('c:/Shift/test_deliverables/datasets/dataset_stress_4gb_plus_wide.csv', header=true)
"""
res = con.execute(query).fetchone()
print(f"Total Rows: {res[0]:,}")
print(f"Total Gross: {res[1]:,}")
print(f"Total Net: {res[2]:,}")
con.close()
