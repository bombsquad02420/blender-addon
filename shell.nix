let
	pkgs = import <nixpkgs> {};
in

pkgs.mkShellNoCC {
	name = "bombsquad-tools";
	packages = with pkgs; [
		python311
		uv
		gnumake
		entr
		zip
		git-cliff
	];
}
