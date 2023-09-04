import PySimpleGUI as sg
import os
import requests
import csv

# Load station data
data = {
  "Station": {
    "0": "Paya Lebar",
    "1": "Ang Mo Kio",
    "2": "Macritchie Reservoir",
    "3": "Botanic Garden",
    "4": "Lower Peirce Reservoir",
    "5": "Bukit Panjang",
    "6": "Pulau Ubin",
    "7": "Bukit Timah",
    "8": "East Coast Parkway",
    "9": "Marina Barrage",
    "10": "Chai Chee",
    "11": "Changi",
    "12": "Newton",
    "13": "Choa Chu Kang (Central)",
    "14": "Lim Chu Kang",
    "15": "Choa Chu Kang (South)",
    "16": "Marine Parade",
    "17": "Choa Chu Kang (West)",
    "18": "Clementi",
    "19": "Tuas South",
    "20": "Dhoby Ghaut",
    "21": "Pasir Panjang",
    "22": "Jurong Island",
    "23": "Jurong (West)",
    "24": "Nicoll Highway",
    "25": "Jurong Pier",
    "26": "Kent Ridge",
    "27": "Kranji Reservoir",
    "28": "Tengah",
    "29": "Seletar",
    "30": "Pasir Ris (West)",
    "31": "Mandai",
    "32": "Serangoon",
    "33": "Tai Seng",
    "34": "Pasir Ris (Central)",
    "35": "Sentosa Island",
    "36": "Punggol",
    "37": "Queenstown",
    "38": "Sembawang",
    "39": "Tanjong Katong",
    "40": "Somerset (Road)",
    "41": "Tuas West",
    "42": "Toa Payoh",
    "43": "Tuas",
    "44": "Ulu Pandan",
    "45": "Upper Peirce Reservoir"
  },
  "Station_ID": {
    "0": "S06",
    "1": "S109",
    "2": "S07",
    "3": "S120",
    "4": "S08",
    "5": "S64",
    "6": "S106",
    "7": "S90",
    "8": "S107",
    "9": "S108",
    "10": "S61",
    "11": "S24",
    "12": "S111",
    "13": "S114",
    "14": "S112",
    "15": "S121",
    "16": "S113",
    "17": "S11",
    "18": "S50",
    "19": "S115",
    "20": "S118",
    "21": "S116",
    "22": "S117",
    "23": "S44",
    "24": "S119",
    "25": "S33",
    "26": "S71",
    "27": "S66",
    "28": "S23",
    "29": "S25",
    "30": "S29",
    "31": "S40",
    "32": "S36",
    "33": "S43",
    "34": "S94",
    "35": "S60",
    "36": "S81",
    "37": "S77",
    "38": "S80",
    "39": "S78",
    "40": "S79",
    "41": "S82",
    "42": "S88",
    "43": "S89",
    "44": "S35",
    "45": "S69"
  }
}

stations = [data['Station_ID'][key] for key in data['Station']]
base_url = "http://www.weather.gov.sg/files/dailydata/DAILYDATA_"


def generate_links(start_year, start_month, end_year, end_month, selected_station_names):
    station_ids = [data['Station_ID'][str(key)] for key, value in data['Station'].items() if
                   value in selected_station_names]
    links = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == start_year and month < start_month:
                continue
            if year == end_year and month > end_month:
                continue
            date = f"{year}{month:02}"
            for station_id in station_ids:
                links.append(base_url + station_id + "_" + date + ".csv")

    return links


def download_data(start_year, start_month, end_year, end_month, selected_station_names):
    # Check if directory 'output' exists and create if not
    if not os.path.exists("output"):
        os.mkdir("output")

    links = generate_links(start_year, start_month, end_year, end_month, selected_station_names)
    total_links = len(links)

    # Set the max_value of ProgressBar to total number of links
    progress_bar.UpdateBar(0, max=total_links)
    progress_text.Update(f"0/{total_links}")

    for index, link in enumerate(links):
        filename = os.path.basename(link)
        if filename not in os.listdir("output"):
            r = requests.get(link)
            if r.status_code == 200:
                with open(os.path.join("output", filename), "wb") as f:
                    f.write(r.content)
        # Update progress bar and progress text
        progress_bar.UpdateBar(index + 1)
        progress_text.Update(f"{index + 1}/{total_links}")
        sg.Window.refresh(window)  # Forcefully refresh the window
    sg.popup('Download Complete!', f'Data from {start_month}/{start_year} to {end_month}/{end_year} has been stored in the "output" directory.')


def merge_csv_files(filename):
    all_files = [f for f in os.listdir("output") if f.endswith('.csv')]

    if not all_files:
        sg.popup_error("No CSV files found in the 'output' directory.")
        return

    with open(os.path.join("output", f"{filename}.csv"), "w", newline='') as outfile:
        writer = csv.writer(outfile)

        # Write the header from the first file
        with open(os.path.join("output", all_files[0]), "r") as first_file:
            reader = csv.reader(first_file)
            header = next(reader)
            writer.writerow(header)

        # Write all the rows, skipping headers
        for file in all_files:
            with open(os.path.join("output", file), "r") as infile:
                reader = csv.reader(infile)
                next(reader)  # Skip the header
                for row in reader:
                    writer.writerow(row)

    sg.popup('Merge Complete!', f'All CSV files have been merged into "{filename}.csv" in the "output" directory.')


layout = [
    [sg.Text("Select start year and month:"), sg.InputText(key='-START_YEAR-'), sg.InputText(key='-START_MONTH-')],
    [sg.Text("Select end year and month:"), sg.InputText(key='-END_YEAR-'), sg.InputText(key='-END_MONTH-')],
    [sg.Text("Select Stations:"),
     sg.Listbox(values=list(data['Station'].values()), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, size=(20, 15),
                default_values=list(data['Station'].values()), key='-STATIONS-')],
    [sg.ProgressBar(max_value=1, orientation='h', size=(20, 20), key='-PROGRESS-')],
    [sg.Text("0/0", key='-PROGRESS_TEXT-', size=(10,1))],
    [sg.Button("Merge CSVs"), sg.InputText("merged_data", key="-MERGE_FILENAME-", size=(15, 1)), sg.Text(".csv")],
    [sg.Button("Download Data"), sg.Button("Exit")]
]

window = sg.Window("Weather Data Downloader", layout)

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED or event == "Exit":
        break
    elif event == "Download Data":
        try:
            start_year, start_month = int(values["-START_YEAR-"]), int(values["-START_MONTH-"])
            end_year, end_month = int(values["-END_YEAR-"]), int(values["-END_MONTH-"])
            selected_station_names = values['-STATIONS-']

            # Reset progress bar value to 0 before starting download
            progress_bar = window['-PROGRESS-']
            progress_text = window['-PROGRESS_TEXT-']
            progress_bar.UpdateBar(0)

            download_data(start_year, start_month, end_year, end_month, selected_station_names)
        except Exception as e:
            sg.popup_error(f"Error: {e}")
    elif event == "Merge CSVs":
        merge_filename = values["-MERGE_FILENAME-"]
        merge_csv_files(merge_filename)

window.close()
