{ pkgs, lib, config, inputs, ... }:
let
  buildInputs = with pkgs; [
    stdenv.cc.cc
    libuv
    zlib
  ];
in 
{
  env = { LD_LIBRARY_PATH = "${with pkgs; lib.makeLibraryPath buildInputs}"; };
  languages.python.package = pkgs.python312;

  languages.python = {
    enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  scripts.build.exec = ''
    rm -r dist
    python3 -m build 
    uv pip install dist/zlibrary*.whl
  '';

  scripts.test.exec = ''
    python3 src/test.py
  '';

  enterShell = ''
    . .devenv/state/venv/bin/activate
    uv pip install build twine
  '';
}
