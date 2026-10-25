#include <complex.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Offline-only complex-state adjoint gradients. kind: Ry=0, Rz=1, CZ=2. */
static void apply(double complex *s, int d, int kind, int mask, double angle) {
    if (kind == 2) {
        for (int i=0; i<d; ++i) if ((i & mask)==mask) s[i]=-s[i];
    } else if (kind == 1) {
        double complex a=cexp(-I*angle/2), b=conj(a);
        for (int i=0; i<d; ++i) s[i]*=(i & mask) ? b : a;
    } else {
        double c=cos(angle/2), t=sin(angle/2);
        for (int i=0; i<d; ++i) if (!(i & mask)) {
            int j=i|mask;
            double complex a=s[i], b=s[j];
            s[i]=c*a-t*b; s[j]=t*a+c*b;
        }
    }
}

double loss_grad(int n, int gates, const int *kind, const int *mask,
                 const int *param, const double *angles, int parameters,
                 const double *target, double *grad) {
    int d=1<<n;
    double complex *history=calloc((gates+1)*d, sizeof(double complex));
    double complex *lambda=malloc(d*sizeof(double complex));
    if (!history || !lambda) abort();
    history[0]=1;
    for (int g=0; g<gates; ++g) {
        double complex *s=history+(g+1)*d;
        memcpy(s,history+g*d,d*sizeof(double complex));
        apply(s,d,kind[g],mask[g],param[g]<0 ? 0 : angles[param[g]]);
    }
    double complex overlap=0;
    for (int i=0; i<d; ++i) overlap+=target[i]*history[gates*d+i];
    for (int i=0; i<d; ++i) lambda[i]=overlap*target[i];
    memset(grad,0,parameters*sizeof(double));
    for (int g=gates-1; g>=0; --g) {
        double complex *s=history+(g+1)*d;
        if (kind[g]!=2) {
            double complex value=0;
            if (kind[g]==0) {
                for (int i=0; i<d; ++i) if (!(i & mask[g])) {
                    int j=i|mask[g];
                    value+=conj(lambda[i])*(-s[j]/2)+conj(lambda[j])*(s[i]/2);
                }
            } else {
                for (int i=0; i<d; ++i)
                    value+=conj(lambda[i])*s[i]*((i & mask[g]) ? I/2 : -I/2);
            }
            grad[param[g]]=-2*creal(value);
        }
        apply(lambda,d,kind[g],mask[g],param[g]<0 ? 0 : -angles[param[g]]);
    }
    double loss=1-creal(overlap*conj(overlap));
    free(history); free(lambda);
    return loss;
}
