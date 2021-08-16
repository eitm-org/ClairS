import shlex
import os
import sys
from os.path import isfile, abspath
from sys import exit, stderr
from subprocess import check_output, PIPE, Popen
import argparse
import shlex
from subprocess import PIPE
import subprocess
from collections import defaultdict

from argparse import ArgumentParser, SUPPRESS
from collections import Counter, defaultdict
from shared.interval_tree import bed_tree_from, is_region_in
import shared.param as param

def subprocess_popen(args, stdin=None, stdout=PIPE, stderr=stderr, bufsize=8388608):
    return Popen(args, stdin=stdin, stdout=stdout, stderr=stderr, bufsize=bufsize, universal_newlines=True)

def vcf_reader(vcf_fn, contig_name, bed_tree=None):
    homo_variant_set = set()
    variant_set = set()
    homo_variant_info = defaultdict()
    unzip_process = subprocess_popen(shlex.split("gzip -fdc %s" % (vcf_fn)))
    for row in unzip_process.stdout:
        row = row.rstrip()
        if row[0] == '#':
            continue
        columns = row.strip().split('\t')

        ctg_name = columns[0]
        if contig_name and contig_name != ctg_name:
            continue
        pos = int(columns[1])
        ref_base = columns[3]
        alt_base = columns[4]
        if bed_tree and not is_region_in(tree=bed_tree, contig_name=contig_name,region_start=pos):
            continue

        genotype_info = columns[9].split(':')
        genotype = genotype_info[0]
        g1, g2 = genotype.replace('|', "/").split('/')
        if g1 == "1" and g2 == "1":
            homo_variant_set.add(pos)
            homo_variant_info[pos] = (ref_base,alt_base)
        variant_set.add(pos)
    return homo_variant_set, homo_variant_info, variant_set

split_bed_size = 2000


def decode_af(input_dir, file_list, output_depth=False, output_alt=False, bed_tree=None, contig_name=None):
    af_list = []
    af_dict = defaultdict(float)
    pos_set = set()
    for f in file_list:
        f = os.path.join(input_dir, f)
        if not os.path.exists(f):
            print('{} not exist'.format(f))
        for row in open(f):
            if output_alt:
                row = row.rstrip().split('\t')
                if len(row) < 5:
                    continue
                pos = row[1]

                af = row[4].split(',')[0]
                af_dict[pos] = float(af)
            else:
                row = row.rstrip().split()
                pos = row[1]
                depth = row[3]
                if bed_tree and not is_region_in(bed_tree, contig_name, int(pos)):
                    continue
                min_depth = 4
                if int(depth) < min_depth:
                    continue
                pos_set.add(int(pos))
    if output_alt:
        return af_dict
    return pos_set

def cal_homo(args):

    contig_name =args.ctgName
    #tumor bed fn
    bed_fn = args.bed_fn
    normal_sample = args.normal_sample
    tumor_sample = args.tumor_sample
    reference_cans = args.reference_cans
    input_dir = args.input_dir
    unified_vcf_fn = args.unified_vcf_fn
    add_truths = args.add_truths
    from shared.vcf import VcfReader
    unified_vcf_reader = VcfReader(vcf_fn=unified_vcf_fn, ctg_name=contig_name, is_var_format=False)
    unified_vcf_reader.read_vcf()
    unified_variant_dict = unified_vcf_reader.variant_dict

    normal_unified_vcf_fn = args.normal_unified_vcf_fn
    normal_unified_vcf_reader = VcfReader(vcf_fn=normal_unified_vcf_fn, ctg_name=contig_name, is_var_format=False)
    normal_unified_vcf_reader.read_vcf()
    normal_unified_variant_dict = normal_unified_vcf_reader.variant_dict

    file_list = os.listdir(input_dir)
    file_list = [f for f in file_list if "_" + contig_name + "_" in f]
    normal_file_list = [f for f in file_list if f.startswith(normal_sample)]
    tumor_file_list = [f for f in file_list if f.startswith(tumor_sample)]
    bed_tree = bed_tree_from(bed_file_path=bed_fn, contig_name=contig_name)

    normal_pos_set = decode_af(input_dir, normal_file_list, output_alt=False, bed_tree=bed_tree, contig_name=contig_name)
    tumor_pos_set = decode_af(input_dir, tumor_file_list, output_alt=False, bed_tree=bed_tree, contig_name=contig_name)

    match_count = 0
    reference_cans_fp = open(reference_cans, 'w')
    pos_in_normal_truth = 0
    pos_in_tumor_truth = 0
    pos_in_normal_truth_and_tumor_truth = 0
    for pos in sorted(list(tumor_pos_set)):
        if pos in normal_unified_variant_dict:
            pos_in_normal_truth += 1
            if pos in unified_variant_dict:
                pos_in_normal_truth_and_tumor_truth += 1
                pos_in_tumor_truth += 1
            # continue
        # skip position in truth if not add truths
        if pos in unified_variant_dict:
            pos_in_tumor_truth += 1
        if pos in unified_variant_dict and not add_truths:
            continue
        reference_cans_fp.write('\t'.join([tumor_sample, contig_name, str(pos)]) + '\n')
        match_count += 1
    print ('[INFO] {} normal pos/tumor pos/matched: {}/{}/{}, pos in normal truth/pos in tumor truth/pos in normal and truth:{}/{}/{}'.format(contig_name, len(normal_pos_set), len(tumor_pos_set), match_count, pos_in_normal_truth, pos_in_tumor_truth, pos_in_normal_truth_and_tumor_truth))


    # depth_set = set([f.split('_')[1] for f in file_list])
    # ctg_set = set([f.split('_')[2] for f in file_list])
    # por_set = set([f.split('_')[3] for f in file_list])

    # intersection_pos_set = homo_variant_set_1.intersection(homo_variant_set_2)
    #
    # same_alt_pos_set = set()
    # for pos in intersection_pos_set:
    #     if homo_variant_info_1[pos] != homo_variant_info_2[pos]:
    #         continue
    #     same_alt_pos_set.add(pos)
    #
    # fp_list = sorted(list(same_alt_pos_set))
    # tp_list = sorted(list(homo_variant_set_2 - homo_variant_set_1))
    # # skip hete variant here
    # tp_list = [item for item in tp_list if item not in variant_set_1]
    # for pos_list, file_name in zip([fp_list, tp_list], [fp_fn, tp_fn]):
    #     all_full_aln_regions = []
    #     region_num = len(pos_list) // split_bed_size + 1 if len(
    #         pos_list) % split_bed_size else len(pos_list) // split_bed_size
    #
    #     for idx in range(region_num):
    #         # a windows region for create tensor # samtools mpileup not include last position
    #         split_output = pos_list[idx * split_bed_size: (idx + 1) * split_bed_size]
    #
    #         split_output = [(item - flankingBaseNum, item + flankingBaseNum + 2) for item in
    #                         split_output]
    #
    #         output_path = os.path.join(split_folder, file_name, '{}.{}_{}_{}'.format(contig_name, idx, region_num, file_name))
    #         all_full_aln_regions.append(output_path)
    #         with open(output_path, 'w') as output_file:
    #             output_file.write('\n'.join(
    #                 ['\t'.join([contig_name, str(x[0] - 1), str(x[1] - 1), ]) for x in
    #                  split_output]) + '\n')  # bed format
    #
    #     all_full_aln_regions_path = os.path.join(split_folder, file_name, 'FULL_ALN_FILE_{}'.format( contig_name))
    #     with open(all_full_aln_regions_path, 'w') as output_file:
    #         output_file.write('\n'.join(all_full_aln_regions) + '\n')
    #
    # print ('[INFO] {} total homo reference pos: 1:{}, 2:{}, intersection:{}, inter_same_repre:{}'.format(contig_name, len(homo_variant_set_1), len(homo_variant_set_2), len(intersection_pos_set), len(same_alt_pos_set)))


def main():
    parser = ArgumentParser(description="Generate variant candidate tensors using phased full-alignment")

    parser.add_argument('--platform', type=str, default='ont',
                        help="Sequencing platform of the input. Options: 'ont,hifi,ilmn', default: %(default)s")

    parser.add_argument('--bam_fn', type=str, default="input.bam",  # required=True,
                        help="Sorted BAM file input, required")

    parser.add_argument('--ref_fn', type=str, default="ref.fa",  # required=True,
                        help="Reference fasta file input, required")

    parser.add_argument('--input_dir', type=str, default="PIPE",
                        help="Tensor output, stdout by default, default: %(default)s")

    parser.add_argument('--normal_sample', type=str, default=None,
                        help="Candidate sites VCF file input, if provided, variants will only be called at the sites in the VCF file,  default: %(default)s")

    parser.add_argument('--tumor_sample', type=str, default=None,
                        help="Candidate sites VCF file input, if provided, variants will only be called at the sites in the VCF file,  default: %(default)s")

    parser.add_argument('--unified_vcf_fn', type=str, default=None,
                        help="Candidate sites VCF file input, if provided, variants will only be called at the sites in the VCF file,  default: %(default)s")

    parser.add_argument('--normal_unified_vcf_fn', type=str, default=None,
                        help="Candidate sites VCF file input, if provided, variants will only be called at the sites in the VCF file,  default: %(default)s")

    parser.add_argument('--min_af', type=float, default=0.08,
                        help="Minimum allele frequency for both SNP and Indel for a site to be considered as a condidate site, default: %(default)f")

    parser.add_argument('--ctgName', type=str, default=None,
                        help="The name of sequence to be processed, required if --bed_fn is not defined")

    parser.add_argument('--reference_cans', type=str, default=None,
                        help="The name of sequence to be processed, required if --bed_fn is not defined")

    parser.add_argument('--ctgStart', type=int, default=None,
                        help="The 1-based starting position of the sequence to be processed, optional, will process the whole --ctgName if not set")

    parser.add_argument('--ctgEnd', type=int, default=None,
                        help="The 1-based inclusive ending position of the sequence to be processed, optional, will process the whole --ctgName if not set")

    parser.add_argument('--bed_fn', type=str, default=None,
                        help="Call variant only in the provided regions. Will take an intersection if --ctgName and/or (--ctgStart, --ctgEnd) are set")

    parser.add_argument('--split_folder', type=str, default=None,
                        help="Call variant only in the provided regions. Will take an intersection if --ctgName and/or (--ctgStart, --ctgEnd) are set")

    parser.add_argument('--sampleName', type=str, default="SAMPLE",
                        help="Define the sample name to be shown in the GVCF file")

    parser.add_argument('--samtools', type=str, default="samtools",
                        help="Path to the 'samtools', samtools version >= 1.10 is required. default: %(default)s")

    parser.add_argument('--fp_fn', type=str, default="fp",
                        help="Path to the 'samtools', samtools version >= 1.10 is required. default: %(default)s")

    parser.add_argument('--tp_fn', type=str, default="tp",
                        help="Path to the 'samtools', samtools version >= 1.10 is required. default: %(default)s")

    parser.add_argument('--output_dir', type=str, default="",
                        help="Path to the 'samtools', samtools version >= 1.10 is required. default: %(default)s")

    # options for advanced users
    parser.add_argument('--minCoverage', type=float, default=2,
                        help="EXPERIMENTAL: Minimum coverage required to call a variant, default: %(default)f")

    parser.add_argument('--minMQ', type=int, default=5,
                        help="EXPERIMENTAL: If set, reads with mapping quality with <$minMQ are filtered, default: %(default)d")

    parser.add_argument('--minBQ', type=int, default=0,
                        help="EXPERIMENTAL: If set, bases with base quality with <$minBQ are filtered, default: %(default)d")

    parser.add_argument('--max_depth', type=int, default=144,
                        help="EXPERIMENTAL: Maximum full alignment depth to be processed. default: %(default)s")

    parser.add_argument('--flankingBaseNum', type=int, default=None,
                        help="EXPERIMENTAL: Maximum full alignment depth to be processed. default: %(default)s")

    # options for debug purpose
    parser.add_argument('--phasing_info_in_bam', action='store_true',
                        help="DEBUG: Skip phasing and use the phasing info provided in the input BAM (HP tag), default: False")

    parser.add_argument('--add_truths', action='store_true',
                        help="DEBUG: Skip phasing and use the phasing info provided in the input BAM (HP tag), default: False")

    parser.add_argument('--extend_bed', type=str, default=None,
                        help="DEBUG: Extend the regions in the --bed_fn by a few bp for tensor creation, default extend 16bp")

    parser.add_argument('--indel_fn', type=str, default=None,
                        help="DEBUG: Output all alternative indel cigar for debug purpose")

    parser.add_argument('--base_err', default=0.001, type=float,
                        help='DEBUG: Estimated base error rate in gvcf option, default: %(default)f')

    parser.add_argument('--gq_bin_size', default=5, type=int,
                        help='DEBUG: Default gq bin size for merge non-variant block in gvcf option, default: %(default)d')

    parser.add_argument('--bp_resolution', action='store_true',
                        help="DEBUG: Enable bp resolution for GVCF, default: disabled")


    args = parser.parse_args()

    cal_homo(args)


if __name__ == "__main__":
    main()
