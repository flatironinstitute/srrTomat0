import asyncio
import os
import subprocess

import numpy as np

from srrTomat0.processor.utils import get_file_from_url, file_path_abs, get_genome_file_locs

STAR_EXECUTABLE = "STAR"

STAR_COUNT_FILE_NAME = "ReadsPerGene.out.tab"
STAR_COUNT_FILE_METAINDEXES = ["N_unmapped", "N_multimapping", "N_noFeature", "N_ambiguous"]
STAR_COUNT_FILE_HEADER = ["Total", "MinusStrand", "PlusStrand"]
STAR_COUNT_COLUMN = "Total"

STAR_DEFAULT_MKREF_OPTIONS = []
STAR_DEFAULT_COUNT_OPTIONS = []


# TODO: test this
def star_align_fastqs(srr_ids, fastq_file_names, reference_genome, output_path, num_workers=4, threads_per_worker=5):
    """
    Take a set of FASTQ files and align them with the STAR aligner (in quantMode)

    :param srr_ids: list(str)
        NCBI SRR ID string
    :param fastq_file_names: list(list(str))
        A list of complete FASTQ file names that were unpacked from the SRR file (including path)
    :param reference_genome: str
        A path to the STAR reference genome that was preassembled
    :param output_path: str
        The path to put the output alignment files
    :param num_workers: int
        Number of separate simultaneous jobs to run
    :param threads_per_worker: int
        Number of threads to assign to each job in STAR (--runThreadN)
    :return count_file_name: str
        The STAR count file generated by --quantMode (including path)
    """

    sem = asyncio.Semaphore(num_workers)

    # Build output paths for STAR from SRR ids
    output_paths = list(map(lambda x: os.path.join(output_path, x), srr_ids))

    # Build STAR tasks
    tasks = [_star_align(sid, fqfn, reference_genome, sout, sem, threads_per_worker=threads_per_worker) for
             sid, fqfn, sout in zip(srr_ids, fastq_file_names, output_paths)]

    # Run and return STAR tasks
    return [asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))]


# TODO: test this
async def _star_align(srr_id, fastq_file_names, reference_genome, output_path, semaphore,
                      threads_per_worker=5, star_options=STAR_DEFAULT_COUNT_OPTIONS):
    """
    Align an individual set of FASTQs from an SRA to the reference genome and get the count data
    :param srr_id: str
        NCBI SRR ID string
    :param fastq_file_names: list(str)
        A list of FASTQ files for the SRR ID
    :param reference_genome: str
        A path to the STAR reference genome
    :param output_path: str
        A path to the output
    :param semaphore: asyncio.Semaphore
        Semaphore for resource utilization
    :param threads_per_worker: int
        Number of threads to assign to each job in STAR (--runThreadN)
    :param star_options: list(str)
        A list of options to pass to the STAR aligner
    :return output_file: str
        The path to the GeneCount file generated by STAR
    """
    async with semaphore:

        output_file = os.path.join(file_path_abs(output_path), STAR_COUNT_FILE_NAME)

        if os.path.exists(output_file):
            print("{id} countfile exists ({path})".format(id=srr_id, path=output_path))
            return output_file

        # Build the STAR executable call
        star_call = [STAR_EXECUTABLE,
                     "--runThreadN", str(threads_per_worker),
                     "--runMode", "alignReads",
                     "--readFilesCommand", "zcat",
                     "--quantMode", "GeneCounts",
                     "--genomeDir", reference_genome,
                     "--outFileNamePrefix", file_path_abs(output_path),
                     "--outFilterType", "BySJout",
                     "--readFilesIn", *fastq_file_names]

        # Add in any additional options
        star_call.extend(star_options)

        print(" ".join(star_call))
        process = await asyncio.create_subprocess_exec(*star_call)
        code = await process.wait()

        if int(code) != 0:
            raise ValueError("STAR failed for {id} ({files})".format(id=srr_id, files=" ".join(fastq_file_names)))

        return output_file


# TODO: test this
def star_mkref(output_path, genome_file=None, annotation_file=None, default_genome=None,
               star_options=STAR_DEFAULT_MKREF_OPTIONS, cores=1, gff_annotations=None, star_executable=STAR_EXECUTABLE):
    """
    Make a reference genome index for STAR to align reads to
    :param output_path: str
        Path to output reference index into
    :param genome_file: str
        Genome sequences (usually FASTA)
    :param annotation_file: str
        Annotation file (usually GTF or GFF)
    :param default_genome: str
        A string to identify one of the common genomes
        This will cause the genome data to be downloaded from ENSEMBL
    :param star_options: list
        A list of additional options to pass to STAR
    :param cores: int
        Number of cores to pass to STAR
    :param gff_annotations: bool
        Flag for GFF3 (instead of GTF) annotations. If None, it will autodetect .gff files.
    :param star_executable: str
        Path to the STAR executable
    :return output_path: str
        Location where the reference genome has been created
    """

    # Get default genome files from the internet if needed
    if (genome_file is None or annotation_file is None) and default_genome is None:
        raise ValueError("star_mkref() requires (genome_file AND annotation_file) OR default_genome to be passed")
    elif default_genome is not None:
        ((genome_url, genome_file), (annotation_url, annotation_file)) = get_genome_file_locs(default_genome)
        genome_file = get_file_from_url(genome_url, genome_file)
        annotation_file = get_file_from_url(annotation_url, annotation_file)

    # Create the output path
    output_path = file_path_abs(output_path)
    try:
        os.makedirs(output_path)
    except FileExistsError:
        pass

    # Uncompress the genome file if it's gzipped
    if genome_file.endswith(".gz"):
        subprocess.call(["gunzip", genome_file])
        genome_file = genome_file[:-3]

    # Uncompress the annotation file if it's gzipped
    if annotation_file.endswith(".gz"):
        subprocess.call(["gunzip", annotation_file])
        annotation_file = annotation_file[:-3]

    # Build the STAR executable call
    star_call = [star_executable,
                 "--runThreadN", str(cores),
                 "--runMode", "genomeGenerate",
                 "--genomeDir", output_path,
                 "--genomeFastaFiles", genome_file,
                 "--sjdbGTFfile", annotation_file]

    # Add any passed-in options
    star_call.extend(star_options)

    # Set a flag for STAR if it's a small genome
    star_sa_idx_size = int(np.floor(np.log2(os.path.getsize(genome_file)) / 2 - 1))
    if star_sa_idx_size < 14:
        star_call.extend(["--genomeSAindexNbases", str(star_sa_idx_size)])

    # Set a flag for STAR if the annotation file is GFF3
    if (gff_annotations is None and ".gff" in annotation_file) or gff_annotations:
        star_call.extend(["--sjdbGTFtagExonParentTranscript", "Parent"])

    # Execute STAR
    print(" ".join(star_call))
    subprocess.call(star_call)

    # Clean up the downloaded files if necessary
    if default_genome is not None:
        os.remove(genome_file)
        os.remove(annotation_file)

    return output_path
