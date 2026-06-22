# lean-workspace


## Defines how the system works

lakefile.toml, lake manifest, and lean-toolchain are all config files that defines packages and libarys and lean modules and where executable files go

The LeanWorkspace.lean file serves as the root of the LeanWorkspace folder where lean modules can be imported from the library into the LeanWorkspace.lean

Then the Main.lean just needs to import the LeanWorkspace.lean file to have all the necessary files and modules

This allows it to declutter the main file


