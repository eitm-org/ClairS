import os

from collections import defaultdict
from os.path import abspath
from sys import exit, stderr
from subprocess import check_output, PIPE, Popen
import argparse
import shlex
from subprocess import PIPE
from os.path import isfile, isdir
from textwrap import dedent

IUPAC_base_to_ACGT_base_dict = dict(zip(
    "ACGTURYSWKMBDHVN",
    ("A", "C", "G", "T", "T", "A", "C", "C", "A", "G", "A", "C", "A", "A", "A", "A")
))

IUPAC_base_to_num_dict = dict(zip(
    "ACGTURYSWKMBDHVN",
    (0, 1, 2, 3, 3, 0, 1, 1, 0, 2, 0, 1, 0, 0, 0, 0)
))
BASIC_BASES = set("ACGTU")

WARNING = '\033[93m'
ERROR = '\033[91m'
ENDC = '\033[0m'

def log_error(log):
    return ERROR + log + ENDC

def log_warning(log):
    return WARNING + log + ENDC

def is_file_exists(file_name, suffix=""):
    if not isinstance(file_name, str) or not isinstance(suffix, str):
        return False
    return isfile(file_name + suffix)

def is_folder_exists(folder_name, suffix=""):
    if not isinstance(folder_name, str) or not isinstance(suffix, str):
        return False
    return isdir(folder_name + suffix)


def legal_range_from(param_name, x, min_num=None, max_num=None, exit_out_of_range=False):

    if min_num is not None and x < min_num and exit_out_of_range:
        exit(log_error("[ERROR] parameter --{} {} (minimum {}) out of range".format(param_name, x, min_num)))
    if max_num is not None and x > max_num and exit_out_of_range:
        exit(log_error("[ERROR] parameter --{} {} (maximum:{}) out of range".format(param_name, x, max_num)))
    return

def file_path_from(file_name, suffix="", exit_on_not_found=False, sep="", allow_none=False, is_directory=False):
    if allow_none and file_name is None:
        return None
    if is_directory:
        is_folder_exists(file_name, suffix)
        if exit_on_not_found:
            exit(log_error("[ERROR] directory %s not found" % (file_name + suffix)))
    if is_file_exists(file_name, suffix):
        return abspath(file_name + suffix)
    #allow fn.bam.bai->fn.bai fn.fa.fai->fn.fai
    elif sep != "" and len(sep) == 1:
        file_name_remove_suffix = sep.join(file_name.split(sep)[:-1])
        if is_file_exists(file_name_remove_suffix, suffix):
            return abspath(file_name_remove_suffix + suffix)
    if exit_on_not_found:
        exit(log_error("[ERROR] file %s not found" % (file_name + suffix)))
    return None

def folder_path_from(folder_name, create_not_found=True, exit_on_not_found=False):
    if is_folder_exists(folder_name):
        return abspath(folder_name)
    if exit_on_not_found:
        exit(log_error("[ERROR] folder %s not found" % (folder_name)))
    if create_not_found:
        if not os.path.exists(folder_name):
            os.makedirs(abspath(folder_name), exist_ok=True)
            print("[INFO] Create folder %s" % (folder_name), file=stderr)
            return abspath(folder_name)
    return None


def is_command_exists(command):
    if not isinstance(command, str):
        return False

    try:
        check_output("which %s" % (command), shell=True)
        return True
    except:
        return False


def executable_command_string_from(command_to_execute, exit_on_not_found=False):
    if is_command_exists(command_to_execute):
        return command_to_execute
    if exit_on_not_found:
        exit(log_error("[ERROR] %s executable not found" % (command_to_execute)))
    return None


def subprocess_popen(args, stdin=None, stdout=PIPE, stderr=stderr, bufsize=8388608):
    return Popen(args, stdin=stdin, stdout=stdout, stderr=stderr, bufsize=bufsize, universal_newlines=True)


def str_none(v):
    if v is None:
        return None
    if v.upper() == "NONE":
        return None
    if isinstance(v, str):
        return v

def str2bool(v):
    if v is None:
        return v
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'ture', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'flase', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def region_from(ctg_name, ctg_start=None, ctg_end=None):
    """
    1-based region string [start, end]
    """
    if ctg_name is None:
        return ""
    if (ctg_start is None) != (ctg_end is None):
        return ""

    if ctg_start is None and ctg_end is None:
        return "{}".format(ctg_name)
    return "{}:{}-{}".format(ctg_name, ctg_start, ctg_end)

def reference_sequence_from(samtools_execute_command, fasta_file_path, regions):
    refernce_sequences = []
    region_value_for_faidx = " ".join(regions)

    samtools_faidx_process = subprocess_popen(
        shlex.split("{} faidx {} {}".format(samtools_execute_command, fasta_file_path, region_value_for_faidx))
    )
    while True:
        row = samtools_faidx_process.stdout.readline()
        is_finish_reading_output = row == '' and samtools_faidx_process.poll() is not None
        if is_finish_reading_output:
            break
        if row:
            refernce_sequences.append(row.rstrip())

    # first line is reference name ">xxxx", need to be ignored
    reference_sequence = "".join(refernce_sequences[1:])

    # uppercase for masked sequences
    reference_sequence = reference_sequence.upper()

    samtools_faidx_process.stdout.close()
    samtools_faidx_process.wait()
    if samtools_faidx_process.returncode != 0:
        return None

    return reference_sequence

def vcf_candidates_from(vcf_fn, contig_name=None):

    known_variants_set = set()
    unzip_process = subprocess_popen(shlex.split("gzip -fdc %s" % (vcf_fn)))

    start_pos, end_pos = float('inf'), 0
    for row in unzip_process.stdout:
        if row[0] == '#':
            continue
        columns = row.strip().split(maxsplit=3)
        ctg_name = columns[0]

        if contig_name and ctg_name != contig_name:
            continue
        center_pos = int(columns[1])
        known_variants_set.add(center_pos)
        start_pos = min(start_pos, center_pos)
        end_pos = max(center_pos, end_pos)

    known_variants_list = sorted(list(known_variants_set))
    return known_variants_list

def candidate_position_generator_from(
    candidate,
    flanking_base_num,
    begin_to_end
):
    for position in candidate:
        for i in range(position - (flanking_base_num + 1), position + (flanking_base_num + 1)):
            if i not in begin_to_end:
                begin_to_end[i] = [(position + (flanking_base_num + 1), position)]
            else:
                begin_to_end[i].append((position + (flanking_base_num + 1), position))
        yield position
    yield -1


def samtools_mpileup_generator_from(
    candidate,
    flanking_base_num,
    begin_to_end
):
    for position in candidate:
        for i in range(position - (flanking_base_num + 1), position + (flanking_base_num + 1)):
            if i not in begin_to_end:
                begin_to_end[i] = [(position + (flanking_base_num + 1), position)]
            else:
                begin_to_end[i].append((position + (flanking_base_num + 1), position))
        yield position
    yield -1

def samtools_view_process_from(
    ctg_name,
    ctg_start,
    ctg_end,
    samtools,
    bam_file_path
):
    have_start_and_end_position = ctg_start != None and ctg_end != None
    region_str = ("%s:%d-%d" % (ctg_name, ctg_start, ctg_end)) if have_start_and_end_position else ctg_name

    return subprocess_popen(
        shlex.split("%s view -F 2318 %s %s" % (samtools, bam_file_path, region_str))
    )

class Position(object):
    def __init__(self, ctg_name=None,
                 genotype1=None,
                 genotype2=None,
                 pos=None,
                 ref_base=None,
                 alt_base=None,
                 candidate=False,
                 cigar_count=None,
                 confident_variant=False,
                 depth=None,
                 alt_list=None,
                 af=None,
                 filter=None,
                 af_list=None,
                 alt_type_mapping_dict=None,
                 extra_infos="",
                 qual=None,
                 row_str=None):
        self.ctg_name = ctg_name
        self.pos = pos
        self.reference_bases = ref_base
        self.candidate = candidate

        if candidate == True:
            self.alternate_bases = alt_base
        else:
            self.alternate_bases = [alt_base] if ',' not in alt_base else alt_base.split(',')

        self.start = pos
        self.end = self.pos + len(ref_base)
        self.genotype1 = genotype1
        self.genotype2 = genotype1
        self.genotype = [genotype1, genotype2]
        self.genotype_str = str(genotype1) + '/' + str(genotype2)
        self.cigar_count = cigar_count
        self.confident_variant = confident_variant
        self.read_name_set = set()
        self.depth = depth
        self.variant_hap_dict = defaultdict(defaultdict)
        self.phased_genotype = None
        self.hap_count_dict = defaultdict(int)
        self.alt_list = alt_list
        self.extra_infos = extra_infos
        self.filter = filter
        self.af = af
        self.qual = qual
        self.row_str = row_str
    def update_info(self, ref_base, alt_base, genotype, extra_infos=""):
        self.reference_bases = ref_base
        self.alternate_bases = alt_base
        self.genotype = genotype
        self.extra_infos = extra_infos



class AltInfos(object):
    def __init__(self, pos, ref_base, depth, af_list, alt_dict, tumor_alt_dict, extra_infos=""):
        self.pos = pos
        self.ref_base = ref_base
        self.depth = depth
        self.af_list = af_list
        self.alt_dict = alt_dict
        self.tumor_alt_dict = tumor_alt_dict
        self.extra_infos = extra_infos
        self.max_candidate_af = None
        self.support_alternative_af = None

def output_header(reference_file_path, output_fn=None, sample_name='SAMPLE'):

    header = dedent("""\
            ##fileformat=VCFv4.2
            ##FILTER=<ID=PASS,Description="All filters passed">
            ##FILTER=<ID=LowQual,Description="Low quality variant">
            ##FILTER=<ID=RefCall,Description="Reference call">
            ##FILTER=<ID=Germline,Description="Germline variant">
            ##INFO=<ID=H,Number=0,Type=Flag,Description="Variant found only in one haplotype in the phased reads">
            ##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
            ##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype quality">
            ##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth in the tumor BAM">
            ##FORMAT=<ID=AF,Number=1,Type=Float,Description="Estimated allele frequency in the tumor BAM">
            ##FORMAT=<ID=NAF,Number=1,Type=Float,Description="Estimated allele frequency in the normal BAM">
            ##FORMAT=<ID=NDP,Number=1,Type=Integer,Description="Read depth in the normal BAM">
            ##FORMAT=<ID=AU,Number=1,Type=Integer,Description="Count of A in the tumor BAM">
            ##FORMAT=<ID=CU,Number=1,Type=Integer,Description="Count of C in the tumor BAM">
            ##FORMAT=<ID=GU,Number=1,Type=Integer,Description="Count of G in the tumor BAM">
            ##FORMAT=<ID=TU,Number=1,Type=Integer,Description="Count of T in the tumor BAM">
            """)

    if reference_file_path is not None:
        reference_index_file_path = file_path_from(reference_file_path, suffix=".fai", exit_on_not_found=True, sep='.')
        with open(reference_index_file_path, "r") as fai_fp:
            for row in fai_fp:
                columns = row.strip().split("\t")
                contig_name, contig_size = columns[0], columns[1]
                header += "##contig=<ID=%s,length=%s>" % (contig_name, contig_size) + '\n'

    header += '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t%s' % (sample_name) + '\n'

    if output_fn:
        with open(output_fn, "w") as output_file:
            output_file.write(header)
    else:
        return header

class TensorStdout(object):
    def __init__(self, handle):
        self.stdin = handle

    def __del__(self):
        self.stdin.close()