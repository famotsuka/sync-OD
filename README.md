# Synchronising OD600 of cell cultures using Biomeki7
Repo containing a Python script that generates a Biomeki7 .CSV input file to dilute each cell culture to a target OD600, giving synchronized growth across a 96‑well plate.

# How to run
- Clone the repository and set up the environment with uv
`git clone <https://github.com/famotsuka/sync-OD.git>`
`cd sync-OD`
`uv sync`
- Activate the environment:
`source .venv/bin/activate` 
- It needs an excel file with the ID of each culture per well of a 96-well plate.
- It needs an excel file with the OD600 readings of each well of the 96-well plate.

# Suggested approach:
1) Prepare an Excel file listing the ID of each culture per well. Two columns containing: 
"Destination Well" (e.g., A01, A02, ..., H12)
"post_id" (e.g., cells1, cells2, mutant1, mutant2, ...),
2) Dilute the overnight culture 1:3 in sterile water
(e.g., 100 µL culture + 300 µL H₂O) in a 96‑deep‑well plate,
3) Prepare the OD600 measurement plate:  
Transfer 50 µL of the diluted culture into 50 µL of H₂O in a 96‑well microtiter plate,
4) Measure OD600 using a plate reader (e.g., BioTek Gen5), 
5) Run the script (`python main.py`) to calculate the volume of water needed to dilute each culture to the target OD600.
6) After dilution, the cultures are ready to be inoculated in the growth plate (e.g., 96-deep well plate)
 by adding 100 uL of the diluted culture to 500 uL of growth media (e.g., LB plus antibiotics) in a 96-deep well plate.