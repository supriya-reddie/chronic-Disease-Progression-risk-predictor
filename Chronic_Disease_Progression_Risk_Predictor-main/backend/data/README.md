# Drop your raw CSVs here

Copy your 5 CSV files into this folder using these exact names:

    backend/data/
        web_patients_1500.csv
        web_conditions_1500.csv
        web_encounters_1500.csv
        web_medications_1500.csv
        web_observations_1500.csv

Then run the import from the `backend/` folder:

    node seed/runImport.js

(This works because `CSV_DATA_DIR` in `.env` defaults to `./data`, and
`web_patients_1500.csv` etc. are already recognized filenames in
`seed/runImport.js`.)
