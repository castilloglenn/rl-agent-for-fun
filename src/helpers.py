def print_spaced(*values) -> None:
    double_spaced = "\n\n"
    print(f"{' '.join(map(str, values))}", end=double_spaced)
