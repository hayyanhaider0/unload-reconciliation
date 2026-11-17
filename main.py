from reconcile import main as reconcile
from database.importer import import_data
from report import main as report


def main():
    unloads = reconcile()
    import_data(unloads)
    report()


if __name__ == "__main__":
    main()