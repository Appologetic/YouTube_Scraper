# ----- Python Standard Library -----
from timeit import default_timer as timer
import threading
import queue
from datetime import datetime
from pytz import timezone

# ----- External Dependencies -----
from termcolor import colored
from InquirerPy import inquirer, get_style

# ----- Internal Dependencies -----
from youtube_scraper.core.ad_processing import find_index, process_data
from youtube_scraper.core.selenium_utils import start_webdriver, new_tab
from youtube_scraper.core.youtube_utils import (
    search_for_term,
    get_video_object,
    click_related_video,
)

# ----- Environment Setup -----
process_queue = queue.Queue()  # instantiate queue for processing with threads
downloaded_ads = 0
clicks_without_ad = 1
new = 0
duplicates = 0


# ----- YouTube Scraper Entrypoint -----
def entrypoint():
    # ----- Colored Messages -----
    entry_message = colored(
        "----- Welcome to the M2K YouTube Ad Scraper -----",
        "magenta",
        attrs=["reverse"],
    )
    search_prompt = colored(
        "To begin, please enter the search term you'd like to browse for ads: \n",
        "magenta",
    )
    target_prompt = colored(
        "Next, please specify a number of ads that you would like to scrape:\n",
        "magenta",
    )
    invalid_error = colored("\nERROR 403:\n", "red", attrs=["bold"])
    non_digit = colored(
        "The input you entered was invalid! Please ensure your input is a digit.\n",
        "red",
    )
    invalid_digit = colored(
        "The input you entered was invalid! Please ensure your input is greater than 0.\n",
        "red",
    )
    style = get_style(
        {
            "question": "#ff75b5",
            "questionmark": "#ff75b5",
            "answered_question": "#ff75b5",
            "answermark": "#ff75b5",
        }
    )
    profiles_notice = colored(
        "***PLEASE NOTE:*** \n due to the way that profile data works, profiles will only work on Spencer's computer \n If not on Spencer's home desktop, please select 'no profile' from the options below to run the script",
        "red",
    )

    # ----- Script -----
    print(entry_message)
    search_term = input(search_prompt)
    valid_target = False
    while valid_target == False:
        download_target = input(target_prompt)
        if download_target.isdigit():  # check that target is a number
            if 1 <= int(download_target):  # check that target is greater than 0
                download_target = int(
                    download_target
                )  # set target to be an integer for use later
                valid_target = True
                continue
            else:
                print(
                    invalid_error, invalid_digit
                )  # print error when conditions not met
        else:
            print(invalid_error, non_digit)  # print error when conditions not met
    print(profiles_notice)
    profile = inquirer.select(
        style=style,
        message="Please select which demographic you'd like to check for ads with:",
        choices=[
            "4 YO Female",
            "4 YO Male",
            "6 YO Male",
            "7 YO Female",
            "9 YO Female",
            "10 YO Male",
            "No Profile",
        ],
    ).execute()
    global dataframe
    dataframe = find_index()  # find index or create new dataframe for ads
    date = datetime.now(tz=timezone("MST")).date()
    global start_time
    start_time = timer()
    find_and_process(search_term, download_target, profile, date)
    exit()


def find_and_process(search_term, download_target, profile, date, driver=None):
    # ----- Script -----
    global clicks_without_ad
    no_ad = colored("No ad found in 10 videos, starting again in a new tab...", "red")
    if not driver:  # if no current driver
        try:
            driver = start_webdriver(profile)
        except Exception as e:
            find_and_process(search_term, download_target, profile, date)
    thread = threading.Thread(target=processing_thread)
    clicks = 1
    try:  # first video click
        search_for_term(driver, search_term)
        video_obj = get_video_object(driver)
        thread.start()
        process_queue.put((video_obj, clicks, search_term, profile, date))
    except:
        new_tab(driver)
        find_and_process(search_term, download_target, profile, date, driver=driver)
    while downloaded_ads < download_target:
        clicks += 1
        try:  # if cannot find like related video, recur in new window
            click_related_video(driver, search_term)
        except Exception as e:
            clicks_without_ad = 1
            new_tab(driver)
            process_queue.put(None)
            thread.join()
            find_and_process(search_term, download_target, profile, date, driver=driver)
        try:
            video_obj = get_video_object(driver)
        except:
            clicks_without_ad = 1
            new_tab(driver)
            process_queue.put(None)
            thread.join()
            find_and_process(search_term, download_target, profile, date, driver=driver)
        process_queue.put((video_obj, clicks, search_term, profile, date))
        if clicks_without_ad > 9:
            print(no_ad)
            clicks_without_ad = 0
            new_tab(driver)
            process_queue.put(None)
            thread.join()
            find_and_process(search_term, download_target, profile, date, driver=driver)
    try:
        driver.quit()
        process_queue.put(None)
        thread.join()
        end_time = timer()
        time_in_mins = int(end_time - start_time) / 60
        execution_time = colored(
            "Found {} ads in {} mins.".format(downloaded_ads, time_in_mins), "magenta"
        )
        new_duplicate = colored(
            "Of the found ads, {} were new, and {} were duplicates".format(
                new, duplicates
            ),
            "magenta",
        )
        print(execution_time)
        print(new_duplicate)
        exit(200)
    except Exception as e:
        print("an exception occured ending")
        print(e)
        return


def processing_thread():
    global downloaded_ads
    global dataframe
    global clicks_without_ad
    global new
    global duplicates

    while True:
        task = process_queue.get()  # get process from queue
        if task is None:  # break if the task is none, set when target hit
            break
        video_obj, clicks, search_term, profile, date = task
        processed, dataframe, ad_present, new_ads, duplicate_ads = process_data(
            video_obj, dataframe, clicks, search_term, profile, date
        )
        if ad_present == True:
            clicks_without_ad = 1
        else:
            clicks_without_ad += 1
        downloaded_ads += processed
        new += new_ads
        duplicates += duplicate_ads
