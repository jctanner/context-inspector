# Older base-image Claude shadows newly installed CLI

During task 087 image validation, plain claude resolved the base image's
/home/evaluator/.local/bin/claude (2.1.219), while /usr/local/bin/claude was the
newly installed 2.1.281. Corrected image PATH and explicit runtime executable
selection for both Vertex and OAuth. Build version manifest uses explicit paths.
Real OAuth Claude tool turn through proxy passes with the new installation.
