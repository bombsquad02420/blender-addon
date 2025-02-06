with import <nixpkgs> {};

stdenv.mkDerivation {
	name = "bombsquad-tools";
	buildInputs = [
		entr
		zip
	];
}
