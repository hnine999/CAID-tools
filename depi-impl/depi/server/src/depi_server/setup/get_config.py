import sys
import os

sys.path.append("src")
import depi_server

def run():
    if len(sys.argv) < 3:
        print("Please supply either mem, dolt, or db and a filename")
        return

    if sys.argv[1].lower() not in ["mem", "dolt", "db"]:
        print("Please supply either mem, dolt, or db and a filename")
        return

    config_out = open(sys.argv[2], "w")
    config_dir = os.path.dirname(depi_server.__file__)+"/configs/"

    arg = sys.argv[1].lower()
    if arg == "mem":
        config_file = config_dir+"depi_config_mem.json"
    elif arg == "dolt":
        config_file = config_dir + "depi_config_dolt.json"
    elif arg == "db":
        config_file = config_dir + "depi_mysql.sql"
    else:
        print("Please supply either mem, dolt, or db and a filename")
        return

    for line in open(config_file, "r"):
        print(line.rstrip(), file=config_out)
    config_out.close()

if __name__ == "__main__":
    run()