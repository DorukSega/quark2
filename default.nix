{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    fuse3
    python3
    (python3.withPackages (ps: with ps; [
      fusepy
      matplotlib
      numpy
      torch
    ]))
  ];

  shellHook = ''
    PS1="\u@\[\e[38;5;208;1m\]\h\[\e[0m\]:\w\[\e[38;5;75m\]\\$\[\e[0m\] "
  '';
}
