def print_spaced(msg: str, *args) -> None:
    double_spaced = "\n\n"
    print(f"{msg}{' '.join(map(str, args))}", end=double_spaced)
