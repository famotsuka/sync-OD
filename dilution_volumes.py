import pandas as pd
import os

"""
Generate a Biomek i7-compatible CSV with per-well water volumes to reach TARGET_OD.

Key parameters (edit at top of file):
    TARGET_OD       -- target OD600 for synchronized growth (default: 0.55)
    REMAINING_VOL   -- µL left in well after OD sampling (default: 350)
    CALIBRATION_LIMIT -- upper OD limit of the linear calibration curve (default: 0.170)
    MAX_VOLUME      -- Biomek pipetting hard limit in µL (default: 1200)

Calibration: y = 8.2258x - 0.3098 (plate reader: true OD600, valid up to OD 0.180).
Above the limit, a +20% volume correction is applied per 0.050 OD step.

Usage: python dilution_volumes.py
See README.md for the full experimental protocol.
"""

os.makedirs("biomek_inputs", exist_ok=True)

# Constants
TARGET_OD = 0.55
REMAINING_VOL = 350  # µL remaining after OD reading (400 - 50)
CALIBRATION_LIMIT = 0.170
OD_STEP = 0.025
CORRECTION_PER_STEP = 0.20
MAX_VOLUME = 1200  # µL — Biomek hard limit


def apply_od_correction(row):
    """Apply stepwise volume correction for OD values above calibration limit."""
    od = row['OD_Value']
    volume = row['Volume']

    if od <= CALIBRATION_LIMIT:
        return volume, False, False  # volume, is_corrected, is_undilutable

    steps_above = int((od - CALIBRATION_LIMIT) / OD_STEP) + 1
    correction_multiplier = 1 + (steps_above * CORRECTION_PER_STEP)
    corrected_volume = round(volume * correction_multiplier)

    if corrected_volume > MAX_VOLUME:
        return corrected_volume, True, True  # is_undilutable

    return corrected_volume, True, False


def prompt_user(corrected_wells, undilutable_wells):
    """Warn the user about out-of-range OD wells and ask how to proceed."""
    print("\n" + "="*60)
    print("⚠️  WARNING: Wells above calibration limit (OD > 0.180)")
    print("="*60)

    if corrected_wells:
        print(f"\n  {len(corrected_wells)} well(s) corrected with +20% volume per 0.050 OD step above limit:")
        for well, od, vol, mult in corrected_wells:
            print(f"    {well}  |  OD: {od:.3f}  |  Corrected volume: {vol} µL  |  Multiplier: {mult:.1f}x")

    if undilutable_wells:
        print(f"\n  {len(undilutable_wells)} well(s) exceed the 1300 µL limit and will be DROPPED from the output:")
        for well, od, vol in undilutable_wells:
            print(f"    {well}  |  OD: {od:.3f}  |  Required volume: {vol} µL")

    print("\n  This correction is an approximation and may affect accuracy.")
    print("\n  Options:")
    print("    [1] Proceed with corrected volumes (undilutable wells will be dropped)")
    print("    [2] Cancel — re-dilute high-OD wells and re-measure")
    print("    [3] Cancel — add a new calibration line for high OD values")

    while True:
        choice = input("\n  Enter your choice (1/2/3): ").strip()
        if choice == '1':
            print("\n✅ Proceeding with corrected volumes...\n")
            return True
        elif choice == '2':
            print("\n❌ Cancelled. Please re-dilute the flagged wells and re-run the script.\n")
            return False
        elif choice == '3':
            print("\n❌ Cancelled. Please add a new calibration line for higher OD values and re-run the script.\n")
            return False
        else:
            print("  Invalid input. Please enter 1, 2, or 3.")


def main():
    print("Hello from sync-od!")

    # Load the Excel file containing the ID of each culture per well
    file_path = 'id_example.xlsx'
    data = pd.read_excel(file_path)

    # Load the OD600 file
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

    # Normalize Destination Well format (A1 → A01)
    data['Destination Well'] = (
        data['Destination Well'].str.replace(
            r'([A-H])(\d+)',
            lambda m: f"{m.group(1)}{int(m.group(2)):02d}",
            regex=True
        )
    )

    # Merge OD values into the main data
    data = data.merge(od_dataframe[['Well', 'OD_Value']], left_on='Destination Well', right_on='Well', how='left')
    print("\n- Merged data with OD values:")
    print(data.head())
    print(data.tail())

    # Calculate volume using calibration line (y = 8.2258x - 0.3098) and dilution formula
    true_OD = (8.226 * data['OD_Value']) - 0.31
    data['Volume'] = ((true_OD / TARGET_OD) * REMAINING_VOL - REMAINING_VOL).round().astype(int)
    print("\n- Data with OD and Volume calculations:")
    print(data.head())
    print(data.tail())

    # Save intermediate file
    data.to_csv('biomek_inputs/TEMP_OD_dilution.csv', index=False)

    # Build sync_od_data
    sync_od_data = data[['post_id', 'Destination Well', 'Volume', 'OD_Value']].copy()
    sync_od_data.rename(columns={
        'post_id': 'Name',
        'Destination Well': 'Source Well'
    }, inplace=True)

    sync_od_data['Destination Plate'] = 'Sync_OD'
    sync_od_data['Destination Well'] = sync_od_data['Source Well']
    sync_od_data['Source Plate'] = 'H2O'
    sync_od_data = sync_od_data[['Name', 'Source Plate', 'Source Well', 'Destination Plate', 'Destination Well', 'Volume', 'OD_Value']]

    # Apply low-OD filters (too low to dilute)
    def classify_volume(row):
        od = row['OD_Value']
        if od < 0.085:
            return 'NA'
        elif od < 0.110:
            return 0
        else:
            return row['Volume']

    sync_od_data['Volume'] = sync_od_data.apply(classify_volume, axis=1)
    sync_od_data = sync_od_data[sync_od_data['Volume'] != 'NA']

    # --- OD correction for values above calibration limit ---
    corrected_wells = []
    undilutable_wells = []

    above_limit = sync_od_data['OD_Value'] > CALIBRATION_LIMIT

    if above_limit.any():
        for idx, row in sync_od_data[above_limit].iterrows():
            corrected_vol, is_corrected, is_undilutable = apply_od_correction(row)
            steps_above = int((row['OD_Value'] - CALIBRATION_LIMIT) / OD_STEP) + 1
            multiplier = 1 + (steps_above * CORRECTION_PER_STEP)

            if is_undilutable:
                undilutable_wells.append((row['Source Well'], row['OD_Value'], corrected_vol))
                sync_od_data.at[idx, 'Volume'] = corrected_vol  # temporarily store for reporting
            else:
                sync_od_data.at[idx, 'Volume'] = corrected_vol
                corrected_wells.append((row['Source Well'], row['OD_Value'], corrected_vol, multiplier))

        # Prompt user before proceeding
        proceed = prompt_user(corrected_wells, undilutable_wells)
        if not proceed:
            return

        # Drop undilutable wells silently from output
        undilutable_well_ids = {w[0] for w in undilutable_wells}
        sync_od_data = sync_od_data[~sync_od_data['Source Well'].isin(undilutable_well_ids)]

    # Final type cleanup
    sync_od_data['Volume'] = sync_od_data['Volume'].astype(int)

    print("\n- Final Sync OD Data:")
    print(sync_od_data.head())
    print(sync_od_data.tail())

    # Save outputs
    sync_od_data.to_csv('biomek_inputs/sync_OD_ID.csv', index=False)

    data_without_name = sync_od_data.drop(columns=['Name', 'OD_Value'])
    data_without_name.to_csv('biomek_inputs/sync_OD_biomek.csv', index=False)

    print("\n✅ Files saved to biomek_inputs/")


if __name__ == "__main__":
    main()
