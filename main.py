import pandas as pd
import itertools
import openpyxl
import os

'''''
Script to generate a Biomeki7 .csv input that will dilute each cell culture to a target OD600 for
growth in a time-predicted way.
- Activate the venv:
source .venv/bin/activate 
- It needs an excel file with the Id of each well of a 96-well plate.
- It needs a excel file with the OD600 readings of each well of the 96-well plate.
- Usual approach is to:
1) Prepare the a excel file containing the ID of each cell culture per well: "Destination Well" (e.g., A01, A02, ..., H12) and "post_id" (e.g., cells1, cells2, mutant1, mutant2, ...),
2) Dilute the overnight culture 1:3 in sterile water (100 uL culture + 300 uL H20) in a 96-deep well plate,
3) Take 50 uL of the diluted culture and dilute it in 50 uL of H20 in a 96-microtiter plate,
4) Measure the OD600 in a typical plate reader (e.g., Biotek Gen5), 
5) Then use the script (python main.py) to calculate the volume of water needed to dilute the culture to the target OD600.
6) After dilution, the cultures are ready to be inoculated in the growth plate (e.g., 96-deep well plate)
 by adding 100 uL of the diluted culture to 500 uL of growth media (e.g., LB plus antibiotics) in a 96-deep well plate.
'''''

os.makedirs("biomek_inputs", exist_ok=True)


def main():
    print("Hello from sync-od!")
    # Load the Excel file containing the ID of each possible mutant in the 96-well plate well. 
    file_path = 'FACS_id_example.xlsx'
    data = pd.read_excel(file_path)

    # Load the OD600 file. It contains the OD600 readings.
    # The measurement was done by diluting 50 uL of diluted overnight culture in 50 uL of H20.
    od_file_path = 'example_OD.xlsx'
    od_data = pd.read_excel(od_file_path, index_col=0)
    valid_cols = [col for col in od_data.columns if isinstance(col, int)]
    od_data = od_data[valid_cols]
    print("\n- Data from the Excel file:")
    print(od_data.head())

    # Create a DataFrame for the 96-microtiter plate
    od_dataframe = od_data.stack().reset_index()
    od_dataframe.columns = ['Row', 'Column', 'OD_Value']
    od_dataframe['Column'] = od_dataframe['Column'].astype(int).astype(str).str.zfill(2)
    od_dataframe['Well'] = od_dataframe['Row'] + od_dataframe['Column']
    print("\n- Stacked dataframe with OD values:")
    print(od_dataframe.head()) 
    print(od_dataframe.tail()) 
    
    # Normalize Destination Well (A1 → A01)
    data['Destination Well'] = (
         data['Destination Well'].str.replace(r'([A-H])(\d+)', lambda m: f"{m.group(1)}{int(m.group(2)):02d}", regex=True)
         )
    # Merge OD values into the main data before iterating over unique IDs
    data = data.merge(od_dataframe[['Well', 'OD_Value']], left_on='Destination Well', right_on='Well', how='left')
    print("\n- Merged data with OD values:")
    print(data.head())
    print(data.tail())

    # Calculate the Volume column based on the OD_Value and the given equation, round, and convert to integer
    # OBS.: This equation is valid if the diluted culture was prepared at 400 uL final volume! And then
    # 50 uL was removed for the OD reading (400 - 50 = 350). If the volume is different, the equation
    # can be adjusted accordingly for the remaining volume after OD reading!
    data['Volume'] = (((((8.226 * data['OD_Value']) - 0.31) / 0.55) * 350) - 350).round().astype(int)
    print("\n- Data with OD and Volume calculations:")
    print(data.head())
    print(data.tail())

    # Save the data with OD and Volume calculations to a CSV file before iteration
    import os

    folder = "biomek_inputs"
    if not os.path.exists(folder):
        os.mkdir(folder)

    data.to_csv('biomek_inputs/TEMP_OD_dilution.csv', index=False)

    # Create a new DataFrame with the specified columns
    # Ensure OD_Value is included in sync_od_data
    sync_od_data = data[['post_id', 'Destination Well', 'Volume', 'OD_Value']].copy()
    sync_od_data.rename(columns={
        'post_id': 'Name',
        'Destination Well': 'Source Well'
    }, inplace=True)
    print("\n- Sync OD Data before setting new columns:")
    print(sync_od_data.head())

    # Set the values for the new columns
    sync_od_data['Destination Plate'] = 'Sync_OD'
    sync_od_data['Destination Well'] = sync_od_data['Source Well']
    sync_od_data['Source Plate'] = 'H2O'

    # Reorder columns to match the desired format
    sync_od_data = sync_od_data[['Name', 'Source Plate', 'Source Well', 'Destination Plate', 'Destination Well', 'Volume', 'OD_Value']]

    # Update Volume based on OD_Value conditions
    sync_od_data['Volume'] = sync_od_data['OD_Value'].apply(
        lambda od: 'NA' if od < 0.085 or od < 0 else (0 if 0.085 <= od < 0.110 else None)
    )

    # Fill in the original Volume values where applicable
    sync_od_data['Volume'] = sync_od_data['Volume'].combine_first(data['Volume'])

    sync_od_data = pd.concat([sync_od_data], ignore_index=True)
    sync_od_data = sync_od_data[sync_od_data['Volume'] != 'NA']
    print("\n- Final Sync OD Data:")
    print(sync_od_data.head())
    print(sync_od_data.tail())

    # Save the first output to the biomek_inputs folder
    sync_od_data.to_csv('biomek_inputs/sync_OD_ID.csv', index=False)

    # Create a second output from data without the column "Name"
    data_without_name = sync_od_data.drop(columns=['Name','OD_Value'])
    data_without_name.to_csv('biomek_inputs/sync_OD_biomek.csv', index=False)



if __name__ == "__main__":
        main()
