/* Overlap and adjoint gradient for synth.py's CZ + Ry ansatz (optional speed-up, loaded via ctypes).
 * Gates in order: kind 0 = ry(theta[param]) on bit mask m1, kind 1 = cz on bit masks m1 | m2.
 * ins, outs: R x dim real states. f = sum_r <out_r|U|in_r> / R. work: 2 * R * dim doubles. */
#include <math.h>
#include <string.h>

static void ry(double *v, int dim, int m, double c, double s) {
    for (int base = 0; base < dim; base += 2 * m)
        for (int i = base; i < base + m; i++) {
            double a = v[i], b = v[i + m];
            v[i] = c * a - s * b;
            v[i + m] = s * a + c * b;
        }
}

static void cz(double *v, int dim, int mm) {
    for (int i = 0; i < dim; i++)
        if ((i & mm) == mm) v[i] = -v[i];
}

void fid_grad(int n, int R, int ng, const int *kind, const int *m1, const int *m2, const int *param,
              const double *theta, int P, const double *ins, const double *outs,
              double *f, double *grad, double *work) {
    int dim = 1 << n;
    double *psi = work, *lam = work + (size_t)R * dim;
    memcpy(psi, ins, sizeof(double) * R * dim);
    for (int i = 0; i < R * dim; i++) lam[i] = outs[i] / R;
    memset(grad, 0, sizeof(double) * P);
    for (int r = 0; r < R; r++) {
        double *v = psi + (size_t)r * dim;
        for (int g = 0; g < ng; g++) {
            if (kind[g]) cz(v, dim, m1[g] | m2[g]);
            else ry(v, dim, m1[g], cos(theta[param[g]] / 2), sin(theta[param[g]] / 2));
        }
    }
    double acc = 0;
    for (int i = 0; i < R * dim; i++) acc += psi[i] * lam[i];
    *f = acc;
    for (int r = 0; r < R; r++) {
        double *v = psi + (size_t)r * dim, *w = lam + (size_t)r * dim;
        for (int g = ng - 1; g >= 0; g--) {
            if (kind[g]) {
                cz(v, dim, m1[g] | m2[g]);
                cz(w, dim, m1[g] | m2[g]);
                continue;
            }
            int m = m1[g];
            double gacc = 0;
            for (int base = 0; base < dim; base += 2 * m)
                for (int i = base; i < base + m; i++) gacc += w[i + m] * v[i] - w[i] * v[i + m];
            grad[param[g]] += 0.5 * gacc;
            double c = cos(theta[param[g]] / 2), s = sin(theta[param[g]] / 2);
            ry(v, dim, m, c, -s);
            ry(w, dim, m, c, -s);
        }
    }
}
