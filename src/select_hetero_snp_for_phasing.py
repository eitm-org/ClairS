# BSD 3-Clause License
#
# Copyright 2023 The University of Hong Kong, Department of Computer Science
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import shlex
import os
import sys
from argparse import ArgumentParser, SUPPRESS
from collections import defaultdict
from subprocess import run

from shared.utils import subprocess_popen

def select_hetero_snp_for_phasing(args):

    tumor_vcf_fn = args.tumor_vcf_fn
    normal_vcf_fn = args.normal_vcf_fn
    var_pct_full = args.var_pct_full
    contig_name = args.ctg_name
    output_folder = args.output_folder
    variant_dict = defaultdict(str)
    tumor_variant_dict = defaultdict(str)
    normal_qual_dict = defaultdict(int)
    tumor_qual_dict = defaultdict(int)
    header = []

    normal_unzip_process = subprocess_popen(shlex.split("gzip -fdc %s" % (normal_vcf_fn)))
    for row in normal_unzip_process.stdout:
        row = row.rstrip()
        if row[0] == '#':
            header.append(row + '\n')
            continue
        columns = row.strip().split()
        ctg_name = columns[0]
        if contig_name and contig_name != ctg_name:
            continue
        pos = int(columns[1])
        ref_base = columns[3]
        alt_base = columns[4]
        genotype = columns[9].split(':')[0].replace('|', '/')

        if len(ref_base) == 1 and len(alt_base) == 1:
            if genotype == '0/1' or genotype == '1/0':
                qual = float(columns[5])
                normal_qual_dict[pos] = qual
                variant_dict[pos] = [ref_base, alt_base, qual, row]

    intersect_pos_set = set()
    hetero_snp_not_found_in_tumor = 0
    hetero_snp_not_match_in_tumor = 0
    tumor_unzip_process = subprocess_popen(shlex.split("gzip -fdc %s" % (tumor_vcf_fn)))
    for row in tumor_unzip_process.stdout:
        row = row.rstrip()
        if row[0] == '#':
            continue
        columns = row.strip().split()
        ctg_name = columns[0]
        if contig_name and contig_name != ctg_name:
            continue
        pos = int(columns[1])
        ref_base = columns[3]
        alt_base = columns[4]
        genotype = columns[9].split(':')[0].replace('|', '/')

        if len(ref_base) == 1 and len(alt_base) == 1:
            if genotype == '0/1' or genotype == '1/0':
                qual = float(columns[5])
                tumor_qual_dict[pos] = qual
                if pos not in variant_dict and qual < args.min_qual:
                    hetero_snp_not_found_in_tumor += 1
                    continue
                if pos in variant_dict:
                    tumor_ref_base, tumor_alt_base = variant_dict[pos][:2]
                    if tumor_ref_base != ref_base or tumor_alt_base != alt_base:
                        hetero_snp_not_match_in_tumor += 1
                        continue
                tumor_variant_dict[pos] = row
                intersect_pos_set.add(pos)

    normal_low_qual_set = set([item[0] for item in sorted(normal_qual_dict.items(), key=lambda x: x[1])[:int(var_pct_full * len(normal_qual_dict))]])
    tumor_low_qual_set = set([item[0] for item in sorted(tumor_qual_dict.items(), key=lambda x: x[1])[:int(var_pct_full * len(tumor_qual_dict))]])


    pass_variant_dict = defaultdict()
    low_qual_count = 0
    for pos in intersect_pos_set:
        if pos in normal_low_qual_set or pos in tumor_low_qual_set:
            low_qual_count += 1
            continue
        pass_variant_dict[pos] = tumor_variant_dict[pos]

    pro = len(pass_variant_dict) / max(len(tumor_qual_dict), 1.0)
    print ('[INFO] Total HET SNP calls selected: {}: {}, not found:{}, not match:{}, low_qual_count:{}. Total normal:{} Total tumor:{}, pro: {}'.format(contig_name, len(pass_variant_dict), hetero_snp_not_found_in_tumor, hetero_snp_not_match_in_tumor, low_qual_count, len(normal_qual_dict), len(tumor_qual_dict), pro))

    if not os.path.exists(output_folder):
        return_code = run("mkdir -p {}".format(output_folder), shell=True)
    f = open(os.path.join(output_folder, '{}.vcf'.format(contig_name)), 'w')
    f.write(''.join(header))
    for key, row in sorted(pass_variant_dict.items(), key=lambda x: x[0]):
        f.write(row +'\n')
    f.close()


def main():
    parser = ArgumentParser(description="Select heterozygous snp candidates for phasing")

    parser.add_argument('--output_folder', type=str, default=None,
                        help="Output folder with all filtered SNP")

    parser.add_argument('--tumor_vcf_fn', type=str, default=None,
                        help="Path of the tumor input vcf file")

    parser.add_argument('--normal_vcf_fn', type=str, default=None,
                        help="Path of the normal input vcf file")

    parser.add_argument('--var_pct_full', type=float, default=0.00,
                        help="Default the low quality proportion to be removed in phasing")

    parser.add_argument('--ctg_name', type=str, default=None,
                        help="The name of sequence to be processed, default: %(default)s")

    parser.add_argument('--min_qual', type=float, default=5,
                        help=SUPPRESS)

    args = parser.parse_args()

    if len(sys.argv[1:]) == 0:
        parser.print_help()
        sys.exit(1)

    select_hetero_snp_for_phasing(args)


if __name__ == "__main__":
    main()
