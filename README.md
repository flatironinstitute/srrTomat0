# inferelator-prior

This is a set of pipelines to create expression and prior matrices for network inference. They are designed to create
data that is compatible with the [inferelator](https://github.com/flatironinstitute/inferelator) package. 

### Usage

    python -m inferelator_prior.network_from_motifs
    usage: network_from_motifs.py -m motif_PWM_file.meme
                                  -f genome_fasta_file.fasta
                                  -g genome_annotation_file.gtf
                                  -o ~/output/path/prefix
                                  --species {yeast,fly,mouse,human}
                                  -b constraning_bed_file.bed
                                  --cpu num_cores
                                  
This requires a motif PWM database (`-m PATH`), 
a genome to search (both sequence as a FASTA `-f PATH` and annotations `-g PATH`),
and an output prefix for several files (`-o PATH`).
In addition, default settings for a specific species can be set with (`--species`).
A BED file can be provided (`-b PATH`) based on some constraining experiment to restrict searching to specific genomic areas.
This will use multiple cores to search for motifs and process the resulting data.
By default, all available processors will be used, but this can be overridden with `--cpu N`.

### Requirements

In addition to
python dependencies, this package also requires 
[STAR](https://github.com/alexdobin/STAR),
[sra-tools](http://ncbi.github.io/sra-tools/), 
[bedtools](https://bedtools.readthedocs.io/en/latest/),
[samtools](http://www.htslib.org/), and
[fimo](http://meme-suite.org/doc/fimo.html).

